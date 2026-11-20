#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/keysym.h>
#include <lilv/lilv.h>
#include <lv2/atom/atom.h>
#include <lv2/atom/util.h>
#include <lv2/core/lv2.h>
#include <lv2/instance-access/instance-access.h>
#include <lv2/midi/midi.h>
#include <lv2/ui/ui.h>
#include <lv2/urid/urid.h>
#include <lv2/worker/worker.h>
#include <pulse/error.h>
#include <pulse/simple.h>
#include <suil/suil.h>

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <map>
#include <mutex>
#include <sstream>
#include <string>
#include <thread>
#include <unordered_map>
#include <utility>
#include <vector>

namespace fs = std::filesystem;

static constexpr uint32_t SAMPLE_RATE = 44100;
static constexpr uint32_t BLOCK_SIZE = 256;
static constexpr uint32_t ATOM_BYTES = 8192;
static constexpr int STEPS = 32;
static constexpr int PITCHES = 30;
static constexpr int BASE_NOTE = 42;
static constexpr int MOD_SLOTS = 4;
static constexpr double PI = 3.14159265358979323846;

struct Note {
  int step = 0;
  int pitch = 60;
  int length = 1;
  float velocity = 0.8f;
};

struct MidiEvent {
  uint32_t frame = 0;
  std::array<uint8_t, 3> data{};
};

struct ControlInfo {
  uint32_t port = 0;
  std::string symbol;
  std::string name;
  float minimum = 0.0f;
  float maximum = 1.0f;
  float def = 0.0f;
  bool integer = false;
  bool toggled = false;
};

enum class LfoWave { Sine = 0, Triangle = 1, Square = 2, Saw = 3 };

struct ModLane {
  std::string symbol;
  int control = -1;
  std::array<float, STEPS> values{};
  float rate = 1.0f;
  float depth = 0.0f;
  LfoWave wave = LfoWave::Sine;
  bool enabled = false;

  ModLane() { values.fill(0.5f); }
};

class Urids {
 public:
  Urids() {
    mapFeature.handle = this;
    mapFeature.map = &Urids::mapThunk;
    unmapFeature.handle = this;
    unmapFeature.unmap = &Urids::unmapThunk;
    map(LV2_ATOM__Sequence);
    map(LV2_ATOM__Chunk);
    map(LV2_MIDI__MidiEvent);
  }

  LV2_URID map(const char* uri) {
    std::lock_guard<std::mutex> lock(mutex);
    auto found = ids.find(uri);
    if (found != ids.end()) return found->second;
    const LV2_URID id = static_cast<LV2_URID>(strings.size() + 1);
    strings.emplace_back(uri);
    ids[strings.back()] = id;
    return id;
  }

  const char* unmap(LV2_URID id) {
    std::lock_guard<std::mutex> lock(mutex);
    return id > 0 && id <= strings.size() ? strings[id - 1].c_str() : nullptr;
  }

  LV2_URID_Map mapFeature{};
  LV2_URID_Unmap unmapFeature{};

 private:
  static LV2_URID mapThunk(LV2_URID_Map_Handle handle, const char* uri) {
    return static_cast<Urids*>(handle)->map(uri);
  }
  static const char* unmapThunk(LV2_URID_Unmap_Handle handle, LV2_URID id) {
    return static_cast<Urids*>(handle)->unmap(id);
  }

  std::mutex mutex;
  std::unordered_map<std::string, LV2_URID> ids;
  std::vector<std::string> strings;
};

struct WorkerJob { std::vector<uint8_t> bytes; };

class Lv2Host {
 public:
  Lv2Host(Urids& urids, LilvWorld* world) : urids_(urids), world_(world) {
    schedule_.handle = this;
    schedule_.schedule_work = &Lv2Host::scheduleThunk;
    mapFeature_ = {LV2_URID__map, &urids_.mapFeature};
    unmapFeature_ = {LV2_URID__unmap, &urids_.unmapFeature};
    workerFeature_ = {LV2_WORKER__schedule, &schedule_};
    features_[0] = &mapFeature_;
    features_[1] = &unmapFeature_;
    features_[2] = &workerFeature_;
    features_[3] = nullptr;
  }

  ~Lv2Host() { unload(); }

  bool load(const LilvPlugin* plugin, std::string& error) {
    unload();
    plugin_ = plugin;
    if (!plugin_) { error = "No LV2 instrument selected"; return false; }
    const uint32_t count = lilv_plugin_get_num_ports(plugin_);
    portValues_.assign(count, 0.0f);
    audio_.assign(count, std::vector<float>(BLOCK_SIZE, 0.0f));
    atom_.assign(count, std::vector<uint8_t>(ATOM_BYTES, 0));
    portKinds_.assign(count, Kind::Unknown);

    LilvNode* input = lilv_new_uri(world_, LILV_URI_INPUT_PORT);
    LilvNode* output = lilv_new_uri(world_, LILV_URI_OUTPUT_PORT);
    LilvNode* audio = lilv_new_uri(world_, LILV_URI_AUDIO_PORT);
    LilvNode* control = lilv_new_uri(world_, LILV_URI_CONTROL_PORT);
    LilvNode* atomPort = lilv_new_uri(world_, LV2_ATOM__AtomPort);
    LilvNode* midi = lilv_new_uri(world_, LV2_MIDI__MidiEvent);
    LilvNode* integer = lilv_new_uri(world_, LV2_CORE__integer);
    LilvNode* toggled = lilv_new_uri(world_, LV2_CORE__toggled);

    std::vector<float> mins(count), maxs(count), defs(count);
    lilv_plugin_get_port_ranges_float(plugin_, mins.data(), maxs.data(), defs.data());
    controls_.clear();
    audioOutputs_.clear();
    midiInputs_.clear();
    for (uint32_t i = 0; i < count; ++i) {
      const LilvPort* port = lilv_plugin_get_port_by_index(plugin_, i);
      const bool isInput = lilv_port_is_a(plugin_, port, input);
      const bool isOutput = lilv_port_is_a(plugin_, port, output);
      if (lilv_port_is_a(plugin_, port, audio)) {
        portKinds_[i] = isOutput ? Kind::AudioOut : Kind::AudioIn;
        if (isOutput) audioOutputs_.push_back(i);
      } else if (lilv_port_is_a(plugin_, port, control)) {
        portKinds_[i] = isInput ? Kind::ControlIn : Kind::ControlOut;
        float lo = std::isfinite(mins[i]) ? mins[i] : 0.0f;
        float hi = std::isfinite(maxs[i]) ? maxs[i] : 1.0f;
        if (hi <= lo) hi = lo + 1.0f;
        float def = std::isfinite(defs[i]) ? defs[i] : lo;
        portValues_[i] = std::clamp(def, lo, hi);
        if (isInput) {
          const LilvNode* sym = lilv_port_get_symbol(plugin_, port);
          LilvNode* label = lilv_port_get_name(plugin_, port);
          controls_.push_back({i, lilv_node_as_string(sym), label ? lilv_node_as_string(label) : lilv_node_as_string(sym),
                               lo, hi, def, lilv_port_has_property(plugin_, port, integer),
                               lilv_port_has_property(plugin_, port, toggled)});
          lilv_node_free(label);
        }
      } else if (lilv_port_is_a(plugin_, port, atomPort)) {
        portKinds_[i] = isInput ? Kind::AtomIn : Kind::AtomOut;
        if (isInput && lilv_port_supports_event(plugin_, port, midi)) midiInputs_.push_back(i);
      }
    }
    lilv_node_free(input); lilv_node_free(output); lilv_node_free(audio); lilv_node_free(control);
    lilv_node_free(atomPort); lilv_node_free(midi); lilv_node_free(integer); lilv_node_free(toggled);

    if (audioOutputs_.empty() || midiInputs_.empty()) {
      error = "The selected LV2 is not a MIDI instrument";
      plugin_ = nullptr;
      return false;
    }
    instance_ = lilv_plugin_instantiate(plugin_, SAMPLE_RATE, features_);
    if (!instance_) { error = "The LV2 instrument could not be instantiated"; plugin_ = nullptr; return false; }
    worker_ = static_cast<const LV2_Worker_Interface*>(
      lilv_instance_get_extension_data(instance_, LV2_WORKER__interface));
    connectPorts();
    lilv_instance_activate(instance_);
    active_ = true;
    return true;
  }

  void unload() {
    if (instance_) {
      if (active_) lilv_instance_deactivate(instance_);
      lilv_instance_free(instance_);
    }
    instance_ = nullptr;
    plugin_ = nullptr;
    worker_ = nullptr;
    active_ = false;
    controls_.clear();
    jobs_.clear();
  }

  bool ready() const { return instance_ != nullptr; }
  const std::vector<ControlInfo>& controls() const { return controls_; }
  const LilvPlugin* plugin() const { return plugin_; }
  LV2_Handle instanceHandle() const { return instance_ ? lilv_instance_get_handle(instance_) : nullptr; }

  float controlValue(int control) const {
    if (control < 0 || control >= static_cast<int>(controls_.size())) return 0.0f;
    return portValues_[controls_[control].port];
  }

  void setControl(int control, float value) {
    if (control < 0 || control >= static_cast<int>(controls_.size())) return;
    const ControlInfo& info = controls_[control];
    value = std::clamp(value, info.minimum, info.maximum);
    if (info.toggled) value = value >= (info.minimum + info.maximum) * 0.5f ? info.maximum : info.minimum;
    else if (info.integer) value = std::round(value);
    portValues_[info.port] = value;
  }

  bool setControlPort(uint32_t port, float value) {
    for (size_t i = 0; i < controls_.size(); ++i) {
      if (controls_[i].port == port) {
        setControl(static_cast<int>(i), value);
        return true;
      }
    }
    return false;
  }

  uint32_t portIndex(const char* symbol) const {
    if (!plugin_ || !symbol) return LV2UI_INVALID_PORT_INDEX;
    for (uint32_t i = 0; i < portKinds_.size(); ++i) {
      const LilvPort* port = lilv_plugin_get_port_by_index(plugin_, i);
      const LilvNode* portSymbol = lilv_port_get_symbol(plugin_, port);
      if (portSymbol && std::strcmp(lilv_node_as_string(portSymbol), symbol) == 0) return i;
    }
    return LV2UI_INVALID_PORT_INDEX;
  }

  int controlBySymbol(const std::string& symbol) const {
    for (size_t i = 0; i < controls_.size(); ++i) if (controls_[i].symbol == symbol) return static_cast<int>(i);
    return -1;
  }

  void copyControlsFrom(const Lv2Host& other) {
    for (const auto& source : other.controls_) {
      int target = controlBySymbol(source.symbol);
      int origin = other.controlBySymbol(source.symbol);
      if (target >= 0 && origin >= 0) setControl(target, other.controlValue(origin));
    }
  }

  void run(uint32_t frames, const std::vector<MidiEvent>& midiEvents,
           const std::array<ModLane, MOD_SLOTS>& mods, double patternPhase) {
    if (!instance_) return;
    for (uint32_t i = 0; i < portKinds_.size(); ++i) {
      if (portKinds_[i] == Kind::AudioIn || portKinds_[i] == Kind::AudioOut)
        std::fill(audio_[i].begin(), audio_[i].begin() + frames, 0.0f);
      else if (portKinds_[i] == Kind::AtomIn) initializeInputSequence(i);
      else if (portKinds_[i] == Kind::AtomOut) initializeOutputAtom(i);
    }
    for (const auto& lane : mods) applyMod(lane, patternPhase);
    for (uint32_t port : midiInputs_) for (const auto& event : midiEvents) appendMidi(port, event);
    lilv_instance_run(instance_, frames);
    processWorkers();
  }

  void stereo(uint32_t frames, std::vector<float>& left, std::vector<float>& right) const {
    left.assign(frames, 0.0f); right.assign(frames, 0.0f);
    if (audioOutputs_.empty()) return;
    const auto& l = audio_[audioOutputs_[0]];
    const auto& r = audio_[audioOutputs_.size() > 1 ? audioOutputs_[1] : audioOutputs_[0]];
    std::copy_n(l.begin(), frames, left.begin());
    std::copy_n(r.begin(), frames, right.begin());
  }

 private:
  enum class Kind { Unknown, AudioIn, AudioOut, ControlIn, ControlOut, AtomIn, AtomOut };

  void connectPorts() {
    for (uint32_t i = 0; i < portKinds_.size(); ++i) {
      void* data = &portValues_[i];
      if (portKinds_[i] == Kind::AudioIn || portKinds_[i] == Kind::AudioOut) data = audio_[i].data();
      else if (portKinds_[i] == Kind::AtomIn || portKinds_[i] == Kind::AtomOut) data = atom_[i].data();
      lilv_instance_connect_port(instance_, i, data);
    }
  }

  void initializeInputSequence(uint32_t port) {
    auto* seq = reinterpret_cast<LV2_Atom_Sequence*>(atom_[port].data());
    seq->atom.type = urids_.map(LV2_ATOM__Sequence);
    seq->atom.size = sizeof(LV2_Atom_Sequence_Body);
    seq->body.unit = 0; seq->body.pad = 0;
  }

  void initializeOutputAtom(uint32_t port) {
    auto* atom = reinterpret_cast<LV2_Atom*>(atom_[port].data());
    atom->type = urids_.map(LV2_ATOM__Chunk);
    atom->size = ATOM_BYTES - sizeof(LV2_Atom);
  }

  void appendMidi(uint32_t port, const MidiEvent& midi) {
    struct Event3 { LV2_Atom_Event event; uint8_t data[3]; uint8_t pad[5]; } packet{};
    packet.event.time.frames = midi.frame;
    packet.event.body.type = urids_.map(LV2_MIDI__MidiEvent);
    packet.event.body.size = 3;
    std::copy(midi.data.begin(), midi.data.end(), packet.data);
    auto* seq = reinterpret_cast<LV2_Atom_Sequence*>(atom_[port].data());
    lv2_atom_sequence_append_event(seq, ATOM_BYTES, &packet.event);
  }

  void applyMod(const ModLane& lane, double phase) {
    int control = lane.control;
    if (!lane.enabled || control < 0 || control >= static_cast<int>(controls_.size())) return;
    const auto& info = controls_[control];
    int step = std::clamp(static_cast<int>(phase * STEPS), 0, STEPS - 1);
    float normalized = lane.values[step];
    double cycle = phase * lane.rate;
    double fraction = cycle - std::floor(cycle);
    double lfo = 0.0;
    switch (lane.wave) {
      case LfoWave::Sine: lfo = std::sin(2.0 * PI * fraction); break;
      case LfoWave::Triangle: lfo = 1.0 - 4.0 * std::abs(fraction - 0.5); break;
      case LfoWave::Square: lfo = fraction < 0.5 ? 1.0 : -1.0; break;
      case LfoWave::Saw: lfo = fraction * 2.0 - 1.0; break;
    }
    normalized = std::clamp(normalized + static_cast<float>(lfo) * lane.depth, 0.0f, 1.0f);
    setControl(control, info.minimum + normalized * (info.maximum - info.minimum));
  }

  static LV2_Worker_Status scheduleThunk(LV2_Worker_Schedule_Handle handle, uint32_t size, const void* data) {
    auto* self = static_cast<Lv2Host*>(handle);
    WorkerJob job;
    job.bytes.resize(size);
    if (size && data) std::memcpy(job.bytes.data(), data, size);
    self->jobs_.push_back(std::move(job));
    return LV2_WORKER_SUCCESS;
  }

  static LV2_Worker_Status respondThunk(LV2_Worker_Respond_Handle handle, uint32_t size, const void* data) {
    auto* self = static_cast<Lv2Host*>(handle);
    if (self->worker_ && self->worker_->work_response)
      return self->worker_->work_response(self->instance_->lv2_handle, size, data);
    return LV2_WORKER_ERR_UNKNOWN;
  }

  void processWorkers() {
    if (worker_ && worker_->work) {
      while (!jobs_.empty()) {
        WorkerJob job = std::move(jobs_.front());
        jobs_.erase(jobs_.begin());
        worker_->work(instance_->lv2_handle, &Lv2Host::respondThunk, this,
                      static_cast<uint32_t>(job.bytes.size()), job.bytes.data());
      }
      if (worker_->end_run) worker_->end_run(instance_->lv2_handle);
    } else {
      jobs_.clear();
    }
  }

  Urids& urids_;
  LilvWorld* world_ = nullptr;
  const LilvPlugin* plugin_ = nullptr;
  LilvInstance* instance_ = nullptr;
  bool active_ = false;
  std::vector<Kind> portKinds_;
  std::vector<float> portValues_;
  std::vector<std::vector<float>> audio_;
  std::vector<std::vector<uint8_t>> atom_;
  std::vector<uint32_t> audioOutputs_;
  std::vector<uint32_t> midiInputs_;
  std::vector<ControlInfo> controls_;
  const LV2_Worker_Interface* worker_ = nullptr;
  std::vector<WorkerJob> jobs_;
  LV2_Worker_Schedule schedule_{};
  LV2_Feature mapFeature_{};
  LV2_Feature unmapFeature_{};
  LV2_Feature workerFeature_{};
  const LV2_Feature* features_[4]{};
};

struct PluginEntry { const LilvPlugin* plugin; std::string uri; std::string name; };

class App {
 public:
  App() : world(lilv_world_new()), host(urids, world) {
    lilv_world_load_all(world);
    discoverPlugins();
    configDir = fs::path(std::getenv("HOME") ? std::getenv("HOME") : "/tmp") / ".config/temporaman-lv2";
    fs::create_directories(configDir);
    loadPattern();
  }

  ~App() {
    quit = true;
    if (audioThread.joinable()) audioThread.join();
    savePattern();
    host.unload();
    if (world) lilv_world_free(world);
  }

  int run() {
    if (plugins.empty()) {
      std::fprintf(stderr, "No compatible LV2 instruments were found.\n");
      return 1;
    }
    if (!host.ready()) loadPlugin(pluginIndex);
    display = XOpenDisplay(nullptr);
    if (!display) { std::fprintf(stderr, "Cannot open X display.\n"); return 1; }
    screen = DefaultScreen(display);
    window = XCreateSimpleWindow(display, RootWindow(display, screen), 100, 80, WIDTH, HEIGHT, 1,
                                 BlackPixel(display, screen), color(0x20242e));
    XStoreName(display, window, "Temporaman LV2 Piano Roll");
    XClassHint hint{}; hint.res_name = const_cast<char*>("temporaman-lv2"); hint.res_class = const_cast<char*>("TemporamanLV2");
    XSetClassHint(display, window, &hint);
    XSelectInput(display, window, ExposureMask | ButtonPressMask | ButtonReleaseMask |
                 PointerMotionMask | KeyPressMask | KeyReleaseMask | StructureNotifyMask);
    wmDelete = XInternAtom(display, "WM_DELETE_WINDOW", False);
    XSetWMProtocols(display, window, &wmDelete, 1);
    gc = XCreateGC(display, window, 0, nullptr);
    font = XLoadQueryFont(display, "fixed");
    if (font) XSetFont(display, gc, font->fid);
    XMapWindow(display, window);
    uiHost = suil_host_new(&App::uiWriteThunk, &App::uiPortIndexThunk, nullptr, nullptr);
    audioThread = std::thread(&App::audioLoop, this);
    while (!quit) {
      while (XPending(display)) {
        XEvent event;
        XNextEvent(display, &event);
        handle(event);
      }
      idleNativeUi();
      std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }
    closeNativeUi();
    if (uiHost) { suil_host_free(uiHost); uiHost = nullptr; }
    XFreeGC(display, gc);
    if (font) XFreeFont(display, font);
    XDestroyWindow(display, window);
    XCloseDisplay(display);
    return 0;
  }

 private:
  static constexpr int WIDTH = 1040;
  static constexpr int HEIGHT = 700;
  static constexpr int GRID_X = 112;
  static constexpr int GRID_Y = 150;
  static constexpr int GRID_W = 896;
  static constexpr int GRID_H = 450;

  unsigned long color(uint32_t rgb) {
    auto found = colorCache.find(rgb);
    if (found != colorCache.end()) return found->second;
    XColor c{}; c.red = ((rgb >> 16) & 0xff) * 257; c.green = ((rgb >> 8) & 0xff) * 257; c.blue = (rgb & 0xff) * 257;
    XAllocColor(display, DefaultColormap(display, DefaultScreen(display)), &c);
    colorCache[rgb] = c.pixel;
    return c.pixel;
  }

  void discoverPlugins() {
    const LilvPlugins* all = lilv_world_get_all_plugins(world);
    LilvNode* input = lilv_new_uri(world, LILV_URI_INPUT_PORT);
    LilvNode* output = lilv_new_uri(world, LILV_URI_OUTPUT_PORT);
    LilvNode* audio = lilv_new_uri(world, LILV_URI_AUDIO_PORT);
    LilvNode* atom = lilv_new_uri(world, LV2_ATOM__AtomPort);
    LilvNode* midi = lilv_new_uri(world, LV2_MIDI__MidiEvent);
    LILV_FOREACH(plugins, i, all) {
      const LilvPlugin* plugin = lilv_plugins_get(all, i);
      bool hasMidi = false, hasAudio = false;
      const uint32_t ports = lilv_plugin_get_num_ports(plugin);
      for (uint32_t p = 0; p < ports; ++p) {
        const LilvPort* port = lilv_plugin_get_port_by_index(plugin, p);
        if (lilv_port_is_a(plugin, port, input) && lilv_port_is_a(plugin, port, atom) &&
            lilv_port_supports_event(plugin, port, midi)) hasMidi = true;
        if (lilv_port_is_a(plugin, port, output) && lilv_port_is_a(plugin, port, audio)) hasAudio = true;
      }
      if (hasMidi && hasAudio) {
        LilvNode* name = lilv_plugin_get_name(plugin);
        plugins.push_back({plugin, lilv_node_as_uri(lilv_plugin_get_uri(plugin)),
                           name ? lilv_node_as_string(name) : lilv_node_as_uri(lilv_plugin_get_uri(plugin))});
        lilv_node_free(name);
      }
    }
    lilv_node_free(input); lilv_node_free(output);
    lilv_node_free(audio); lilv_node_free(atom); lilv_node_free(midi);
    std::sort(plugins.begin(), plugins.end(), [](const auto& a, const auto& b) { return a.name < b.name; });
  }

  bool loadPlugin(int index) {
    if (plugins.empty()) return false;
    index = (index % static_cast<int>(plugins.size()) + plugins.size()) % static_cast<int>(plugins.size());
    closeNativeUi();
    std::lock_guard<std::recursive_mutex> lock(engineMutex);
    std::string error;
    if (!host.load(plugins[index].plugin, error)) { status = error; return false; }
    pluginIndex = index;
    for (auto& lane : mods) {
      lane.control = lane.symbol.empty() ? -1 : host.controlBySymbol(lane.symbol);
      if (lane.control < 0 && !host.controls().empty()) lane.control = 0;
      if (lane.control >= 0) {
        lane.symbol = host.controls()[lane.control].symbol;
        const auto& c = host.controls()[lane.control];
        float n = (host.controlValue(lane.control) - c.minimum) / (c.maximum - c.minimum);
        if (!lane.enabled) lane.values.fill(n);
      }
    }
    status = "Loaded " + plugins[index].name;
    return true;
  }

  void audioLoop() {
    pa_sample_spec spec{PA_SAMPLE_S16LE, SAMPLE_RATE, 2};
    int error = 0;
    pa_simple* pulse = pa_simple_new(nullptr, "Temporaman LV2", PA_STREAM_PLAYBACK, nullptr,
                                     "LV2 piano roll", &spec, nullptr, nullptr, &error);
    if (!pulse) { status = std::string("Audio unavailable: ") + pa_strerror(error); return; }
    std::vector<float> left, right;
    std::vector<int16_t> interleaved(BLOCK_SIZE * 2);
    while (!quit) {
      std::vector<MidiEvent> events;
      std::array<ModLane, MOD_SLOTS> modSnapshot;
      {
        std::lock_guard<std::recursive_mutex> state(stateMutex);
        events.swap(pendingMidi);
        if (playing) appendPatternEvents(events, BLOCK_SIZE, playFrame);
        modSnapshot = mods;
      }
      {
        std::lock_guard<std::recursive_mutex> lock(engineMutex);
        double phase = patternFrames() ? static_cast<double>(playFrame % patternFrames()) / patternFrames() : 0.0;
        host.run(BLOCK_SIZE, events, modSnapshot, phase);
        host.stereo(BLOCK_SIZE, left, right);
      }
      for (uint32_t i = 0; i < BLOCK_SIZE; ++i) {
        interleaved[i * 2] = static_cast<int16_t>(std::clamp(left[i], -1.0f, 1.0f) * 32767.0f);
        interleaved[i * 2 + 1] = static_cast<int16_t>(std::clamp(right[i], -1.0f, 1.0f) * 32767.0f);
      }
      if (pa_simple_write(pulse, interleaved.data(), interleaved.size() * sizeof(int16_t), &error) < 0) {
        status = std::string("Audio error: ") + pa_strerror(error); break;
      }
      if (playing) playFrame = (playFrame + BLOCK_SIZE) % std::max<uint64_t>(1, patternFrames());
    }
    pa_simple_free(pulse);
  }

  uint64_t stepFrames() const { return static_cast<uint64_t>(SAMPLE_RATE * 60.0 / std::max(20, bpm) / 4.0); }
  uint64_t patternFrames() const { return stepFrames() * STEPS; }

  void appendPatternEvents(std::vector<MidiEvent>& events, uint32_t frames, uint64_t position) {
    const uint64_t length = patternFrames();
    const uint64_t perStep = stepFrames();
    for (const auto& note : notes) {
      uint64_t on = note.step * perStep;
      uint64_t off = ((note.step + note.length) * perStep) % length;
      uint64_t onDelta = (on + length - position) % length;
      uint64_t offDelta = (off + length - position) % length;
      uint8_t velocity = static_cast<uint8_t>(std::clamp(note.velocity, 0.05f, 1.0f) * 127.0f);
      if (offDelta < frames) events.push_back({static_cast<uint32_t>(offDelta), {0x80, static_cast<uint8_t>(note.pitch), 0}});
      if (onDelta < frames) events.push_back({static_cast<uint32_t>(onDelta), {0x90, static_cast<uint8_t>(note.pitch), velocity}});
    }
    std::sort(events.begin(), events.end(), [](const MidiEvent& a, const MidiEvent& b) {
      if (a.frame != b.frame) return a.frame < b.frame;
      return (a.data[0] & 0xf0) < (b.data[0] & 0xf0);
    });
  }

  void queueMidi(uint8_t statusByte, uint8_t note, uint8_t velocity) {
    std::lock_guard<std::recursive_mutex> lock(stateMutex);
    pendingMidi.push_back({0, {statusByte, note, velocity}});
  }

  void stopPlayback() {
    playing = false; playFrame = 0; queueMidi(0xB0, 123, 0); redraw();
  }

  void exportWav() {
    stopPlayback();
    status = "Rendering WAV…"; redraw();
    fs::path outDir = "/srv/audacity-studio/imports";
    fs::create_directories(outDir);
    std::time_t now = std::time(nullptr);
    char stamp[32]; std::strftime(stamp, sizeof(stamp), "%Y%m%d-%H%M%S", std::localtime(&now));
    fs::path target = outDir / (std::string("temporaman-lv2-") + stamp + ".wav");
    Lv2Host renderer(urids, world);
    std::string error;
    {
      std::lock_guard<std::recursive_mutex> lock(engineMutex);
      if (!renderer.load(plugins[pluginIndex].plugin, error)) { status = error; redraw(); return; }
      renderer.copyControlsFrom(host);
    }
    std::ofstream file(target, std::ios::binary);
    if (!file) { status = "Could not create the WAV file"; return; }
    writeWavHeader(file, 0);
    const uint64_t total = patternFrames() + SAMPLE_RATE * 2;
    uint64_t position = 0;
    uint32_t dataBytes = 0;
    std::vector<float> left, right;
    std::vector<int16_t> pcm(BLOCK_SIZE * 2);
    while (position < total) {
      uint32_t frames = static_cast<uint32_t>(std::min<uint64_t>(BLOCK_SIZE, total - position));
      std::vector<MidiEvent> events;
      if (position < patternFrames()) appendPatternEvents(events, frames, position % patternFrames());
      double phase = static_cast<double>(position % patternFrames()) / patternFrames();
      renderer.run(frames, events, mods, phase);
      renderer.stereo(frames, left, right);
      for (uint32_t i = 0; i < frames; ++i) {
        pcm[i * 2] = static_cast<int16_t>(std::clamp(left[i], -1.0f, 1.0f) * 32767.0f);
        pcm[i * 2 + 1] = static_cast<int16_t>(std::clamp(right[i], -1.0f, 1.0f) * 32767.0f);
      }
      file.write(reinterpret_cast<char*>(pcm.data()), frames * 2 * sizeof(int16_t));
      dataBytes += frames * 2 * sizeof(int16_t);
      position += frames;
    }
    file.seekp(0); writeWavHeader(file, dataBytes); file.close();
    status = "Exported " + target.filename().string();
    savePattern(); redraw();
  }

  static void writeU16(std::ostream& out, uint16_t value) { out.put(value & 0xff); out.put((value >> 8) & 0xff); }
  static void writeU32(std::ostream& out, uint32_t value) {
    for (int i = 0; i < 4; ++i) out.put((value >> (i * 8)) & 0xff);
  }
  static void writeWavHeader(std::ostream& out, uint32_t bytes) {
    out.write("RIFF", 4); writeU32(out, 36 + bytes); out.write("WAVEfmt ", 8); writeU32(out, 16);
    writeU16(out, 1); writeU16(out, 2); writeU32(out, SAMPLE_RATE); writeU32(out, SAMPLE_RATE * 4);
    writeU16(out, 4); writeU16(out, 16); out.write("data", 4); writeU32(out, bytes);
  }

  static void uiWriteThunk(SuilController controller, uint32_t port, uint32_t size,
                           uint32_t protocol, const void* buffer) {
    auto* self = static_cast<App*>(controller);
    if (!self || protocol != 0 || size != sizeof(float) || !buffer) return;
    std::lock_guard<std::recursive_mutex> lock(self->engineMutex);
    self->host.setControlPort(port, *static_cast<const float*>(buffer));
  }

  static uint32_t uiPortIndexThunk(SuilController controller, const char* symbol) {
    auto* self = static_cast<App*>(controller);
    return self ? self->host.portIndex(symbol) : LV2UI_INVALID_PORT_INDEX;
  }

  static int uiResizeThunk(LV2UI_Feature_Handle handle, int width, int height) {
    auto* self = static_cast<App*>(handle);
    if (!self || !self->display || !self->nativeUiWindow || width <= 0 || height <= 0) return 1;
    if (self->nativeUiChild) {
      width = std::min(std::max(width, 960), DisplayWidth(self->display, self->screen) - 32);
      height = std::min(std::max(height, 700), DisplayHeight(self->display, self->screen) - 64);
      XResizeWindow(self->display, self->nativeUiChild,
                    static_cast<unsigned>(width), static_cast<unsigned>(height));
    } else {
      XResizeWindow(self->display, self->nativeUiWindow,
                    static_cast<unsigned>(width), static_cast<unsigned>(height));
    }
    return 0;
  }

  void toggleNativeUi() {
    if (nativeUi) {
      if (nativeUiVisible) hideNativeUi();
      else {
        XMapRaised(display, nativeUiChild);
        nativeUiVisible = true;
        status = "Plugin GUI opened";
        redraw();
      }
      return;
    }
    openNativeUi();
  }

  void openNativeUi() {
    if (!display || !uiHost || !host.ready() || !host.plugin()) return;
    LilvUIs* uis = lilv_plugin_get_uis(host.plugin());
    LilvNode* container = lilv_new_uri(world, LV2_UI__X11UI);
    const LilvUI* selected = nullptr;
    const LilvNode* selectedType = nullptr;
    unsigned bestQuality = 0;
    LILV_FOREACH(uis, i, uis) {
      const LilvUI* candidate = lilv_uis_get(uis, i);
      const LilvNode* candidateType = nullptr;
      unsigned quality = lilv_ui_is_supported(candidate, suil_ui_supported, container, &candidateType);
      if (quality && (!bestQuality || quality < bestQuality)) {
        bestQuality = quality;
        selected = candidate;
        selectedType = candidateType;
      }
    }
    if (!selected) {
      status = "This LV2 has no native GUI; use the Mod parameter browser";
      lilv_node_free(container);
      lilv_uis_free(uis);
      redraw();
      return;
    }

    nativeUiWindow = XCreateSimpleWindow(display, RootWindow(display, screen), 145, 110, 960, 650, 1,
                                         BlackPixel(display, screen), BlackPixel(display, screen));
    std::string title = plugins[pluginIndex].name + " — LV2 controls";
    XStoreName(display, nativeUiWindow, title.c_str());
    XClassHint hint{};
    hint.res_name = const_cast<char*>("temporaman-lv2-ui");
    hint.res_class = const_cast<char*>("TemporamanLV2UI");
    XSetClassHint(display, nativeUiWindow, &hint);
    XSetWMProtocols(display, nativeUiWindow, &wmDelete, 1);
    XSelectInput(display, nativeUiWindow, StructureNotifyMask | ExposureMask);

    nativeResize.handle = this;
    nativeResize.ui_resize = &App::uiResizeThunk;
    nativeParentFeature = {LV2_UI__parent, reinterpret_cast<void*>(static_cast<uintptr_t>(nativeUiWindow))};
    nativeInstanceFeature = {LV2_INSTANCE_ACCESS_URI, host.instanceHandle()};
    nativeMapFeature = {LV2_URID__map, &urids.mapFeature};
    nativeUnmapFeature = {LV2_URID__unmap, &urids.unmapFeature};
    nativeResizeFeature = {LV2_UI__resize, &nativeResize};
    const LV2_Feature* features[] = {&nativeParentFeature, &nativeInstanceFeature, &nativeMapFeature,
                                     &nativeUnmapFeature, &nativeResizeFeature, nullptr};
    char* bundle = lilv_file_uri_parse(lilv_node_as_uri(lilv_ui_get_bundle_uri(selected)), nullptr);
    char* binary = lilv_file_uri_parse(lilv_node_as_uri(lilv_ui_get_binary_uri(selected)), nullptr);
    nativeUi = suil_instance_new(uiHost, this, LV2_UI__X11UI,
                                 lilv_node_as_uri(lilv_plugin_get_uri(host.plugin())),
                                 lilv_node_as_uri(lilv_ui_get_uri(selected)), lilv_node_as_uri(selectedType),
                                 bundle, binary, features);
    std::free(bundle);
    std::free(binary);
    lilv_node_free(container);
    lilv_uis_free(uis);
    if (!nativeUi) {
      XDestroyWindow(display, nativeUiWindow);
      nativeUiWindow = 0;
      status = "The LV2 native GUI could not be opened";
      redraw();
      return;
    }
    nativeUiChild = static_cast<Window>(reinterpret_cast<uintptr_t>(suil_instance_get_widget(nativeUi)));
    if (nativeUiChild) {
      XWindowAttributes childAttributes{};
      XGetWindowAttributes(display, nativeUiChild, &childAttributes);
      const int uiWidth = std::min(std::max(childAttributes.width, 960), DisplayWidth(display, screen) - 32);
      const int uiHeight = std::min(std::max(childAttributes.height, 700), DisplayHeight(display, screen) - 64);
      XResizeWindow(display, nativeUiChild,
                    static_cast<unsigned>(uiWidth), static_cast<unsigned>(uiHeight));
      XMoveWindow(display, nativeUiChild, std::max(0, (DisplayWidth(display, screen) - uiWidth) / 2), 20);
    }
    nativeIdle = static_cast<const LV2UI_Idle_Interface*>(
      suil_instance_extension_data(nativeUi, LV2_UI__idleInterface));
    XMapRaised(display, nativeUiChild);
    nativeUiVisible = true;
    lastUiSync = std::chrono::steady_clock::now();
    syncNativeUi();
    status = "Opened the real " + plugins[pluginIndex].name + " controls";
    redraw();
  }

  void hideNativeUi() {
    if (display && nativeUiChild) XUnmapWindow(display, nativeUiChild);
    nativeUiVisible = false;
    status = "Plugin GUI hidden; its sound settings are still active";
    savePattern();
    redraw();
  }

  void closeNativeUi() {
    nativeUiVisible = false;
    nativeIdle = nullptr;
    nativeUiChild = 0;
    if (nativeUi) { suil_instance_free(nativeUi); nativeUi = nullptr; }
    if (display && nativeUiWindow) XDestroyWindow(display, nativeUiWindow);
    nativeUiWindow = 0;
  }

  void syncNativeUi() {
    if (!nativeUi) return;
    std::lock_guard<std::recursive_mutex> lock(engineMutex);
    for (size_t i = 0; i < host.controls().size(); ++i) {
      const auto& control = host.controls()[i];
      float value = host.controlValue(static_cast<int>(i));
      suil_instance_port_event(nativeUi, control.port, sizeof(value), 0, &value);
    }
  }

  void idleNativeUi() {
    if (!nativeUi || !nativeUiVisible) return;
    if (nativeIdle && nativeIdle->idle && nativeIdle->idle(suil_instance_get_handle(nativeUi)) != 0) {
      hideNativeUi();
      return;
    }
    const auto now = std::chrono::steady_clock::now();
    if (now - lastUiSync >= std::chrono::milliseconds(33)) {
      syncNativeUi();
      lastUiSync = now;
    }
  }

  void handle(const XEvent& event) {
    if (event.type == Expose) draw();
    else if (event.type == ClientMessage && static_cast<Atom>(event.xclient.data.l[0]) == wmDelete) {
      if (event.xclient.window == nativeUiWindow) hideNativeUi();
      else if (event.xclient.window == window) quit = true;
    }
    else if (event.type == ButtonPress) { std::lock_guard<std::recursive_mutex> lock(stateMutex); mouseDown(event.xbutton); }
    else if (event.type == ButtonRelease) { std::lock_guard<std::recursive_mutex> lock(stateMutex); mouseUp(event.xbutton); }
    else if (event.type == MotionNotify) { std::lock_guard<std::recursive_mutex> lock(stateMutex); mouseMove(event.xmotion); }
    else if (event.type == KeyPress) { std::lock_guard<std::recursive_mutex> lock(stateMutex); key(event.xkey, true); }
    else if (event.type == KeyRelease) { std::lock_guard<std::recursive_mutex> lock(stateMutex); key(event.xkey, false); }
  }

  void mouseDown(const XButtonEvent& e) {
    if (controlPicker) { pickerMouseDown(e); return; }
    if (buttonHit(e.x, e.y, 10, 12, 44, 28)) { loadPlugin(pluginIndex - 1); syncMods(); savePattern(); redraw(); return; }
    if (buttonHit(e.x, e.y, 58, 12, 44, 28)) { loadPlugin(pluginIndex + 1); syncMods(); savePattern(); redraw(); return; }
    if (buttonHit(e.x, e.y, 850, 12, 176, 28)) { toggleNativeUi(); return; }
    if (buttonHit(e.x, e.y, 10, 52, 70, 30)) { playing = !playing; if (!playing) stopPlayback(); redraw(); return; }
    if (buttonHit(e.x, e.y, 86, 52, 70, 30)) { recording = !recording; redraw(); return; }
    if (buttonHit(e.x, e.y, 162, 52, 70, 30)) { stopPlayback(); return; }
    if (buttonHit(e.x, e.y, 238, 52, 78, 30)) { exportWav(); return; }
    if (buttonHit(e.x, e.y, 322, 52, 65, 30)) { notes.clear(); selectedNote = -1; savePattern(); redraw(); return; }
    if (buttonHit(e.x, e.y, 400, 52, 28, 30)) { bpm = std::max(20, bpm - 5); savePattern(); redraw(); return; }
    if (buttonHit(e.x, e.y, 475, 52, 28, 30)) { bpm = std::min(300, bpm + 5); savePattern(); redraw(); return; }
    if (buttonHit(e.x, e.y, 520, 52, 118, 30)) { view = (view + 1) % (MOD_SLOTS + 1); redraw(); return; }
    if (view == 0) pianoMouseDown(e);
    else modMouseDown(e);
  }

  void pianoMouseDown(const XButtonEvent& e) {
    if (!insideGrid(e.x, e.y)) return;
    int step = std::clamp((e.x - GRID_X) * STEPS / GRID_W, 0, STEPS - 1);
    int row = std::clamp((e.y - GRID_Y) * PITCHES / GRID_H, 0, PITCHES - 1);
    int pitch = BASE_NOTE + PITCHES - 1 - row;
    int found = noteAt(step, pitch);
    if (e.button == Button3) {
      if (found >= 0) notes.erase(notes.begin() + found);
      selectedNote = -1; savePattern(); redraw(); return;
    }
    if (found >= 0) { selectedNote = found; dragging = true; dragStart = notes[found].step; }
    else {
      notes.push_back({step, pitch, defaultLength, defaultVelocity});
      selectedNote = static_cast<int>(notes.size() - 1); dragging = true; dragStart = step;
      queueMidi(0x90, pitch, static_cast<uint8_t>(defaultVelocity * 127));
    }
    redraw();
  }

  void modMouseDown(const XButtonEvent& e) {
    ModLane& lane = mods[view - 1];
    if (buttonHit(e.x, e.y, 10, 106, 40, 28)) { changeModTarget(lane, -1); redraw(); return; }
    if (buttonHit(e.x, e.y, 54, 106, 40, 28)) { changeModTarget(lane, 1); redraw(); return; }
    if (buttonHit(e.x, e.y, 100, 100, 600, 38)) { controlPicker = true; pickerPage = std::max(0, lane.control / PICKER_ROWS); redraw(); return; }
    if (buttonHit(e.x, e.y, 710, 106, 74, 28)) { lane.enabled = !lane.enabled; savePattern(); redraw(); return; }
    if (buttonHit(e.x, e.y, 790, 106, 70, 28)) { lane.wave = static_cast<LfoWave>((static_cast<int>(lane.wave) + 1) % 4); savePattern(); redraw(); return; }
    if (buttonHit(e.x, e.y, 866, 106, 34, 28)) { lane.rate = std::max(0.25f, lane.rate * 0.5f); savePattern(); redraw(); return; }
    if (buttonHit(e.x, e.y, 904, 106, 34, 28)) { lane.rate = std::min(8.0f, lane.rate * 2.0f); savePattern(); redraw(); return; }
    if (buttonHit(e.x, e.y, 942, 106, 34, 28)) { lane.depth = std::max(0.0f, lane.depth - 0.05f); savePattern(); redraw(); return; }
    if (buttonHit(e.x, e.y, 980, 106, 34, 28)) { lane.depth = std::min(0.5f, lane.depth + 0.05f); savePattern(); redraw(); return; }
    if (insideGrid(e.x, e.y)) { setModPoint(lane, e.x, e.y); dragging = true; redraw(); }
  }

  void mouseMove(const XMotionEvent& e) {
    if (!dragging) return;
    if (view == 0 && selectedNote >= 0 && insideGrid(e.x, e.y)) {
      int step = std::clamp((e.x - GRID_X) * STEPS / GRID_W, 0, STEPS - 1);
      notes[selectedNote].length = std::clamp(step - dragStart + 1, 1, STEPS - dragStart);
      redraw();
    } else if (view > 0 && insideGrid(e.x, e.y)) {
      setModPoint(mods[view - 1], e.x, e.y); redraw();
    }
  }

  void mouseUp(const XButtonEvent&) {
    if (dragging && view == 0 && selectedNote >= 0) queueMidi(0x80, notes[selectedNote].pitch, 0);
    dragging = false; savePattern();
  }

  void setModPoint(ModLane& lane, int x, int y) {
    int step = std::clamp((x - GRID_X) * STEPS / GRID_W, 0, STEPS - 1);
    lane.values[step] = std::clamp(1.0f - static_cast<float>(y - GRID_Y) / GRID_H, 0.0f, 1.0f);
    lane.enabled = true;
  }

  void key(const XKeyEvent& event, bool down) {
    KeySym sym = XLookupKeysym(const_cast<XKeyEvent*>(&event), 0);
    if (down && sym == XK_space) { playing = !playing; if (!playing) stopPlayback(); redraw(); return; }
    if (down && sym == XK_Delete && selectedNote >= 0) {
      notes.erase(notes.begin() + selectedNote); selectedNote = -1; savePattern(); redraw(); return;
    }
    const std::string keys = "awsedftgyhujkolp";
    char ch = static_cast<char>(sym);
    auto pos = keys.find(ch);
    if (pos == std::string::npos) return;
    int pitch = 60 + static_cast<int>(pos);
    if (down && !held[pitch]) {
      held[pitch] = true; queueMidi(0x90, pitch, 110);
      if (recording) {
        int step = static_cast<int>((playFrame / std::max<uint64_t>(1, stepFrames())) % STEPS);
        notes.push_back({step, pitch, defaultLength, 110.0f / 127.0f}); selectedNote = notes.size() - 1; redraw();
      }
    } else if (!down && held[pitch]) { held[pitch] = false; queueMidi(0x80, pitch, 0); }
  }

  bool insideGrid(int x, int y) const { return x >= GRID_X && x < GRID_X + GRID_W && y >= GRID_Y && y < GRID_Y + GRID_H; }
  bool buttonHit(int x, int y, int bx, int by, int bw, int bh) const { return x >= bx && x < bx + bw && y >= by && y < by + bh; }
  int noteAt(int step, int pitch) const {
    for (size_t i = 0; i < notes.size(); ++i)
      if (notes[i].pitch == pitch && step >= notes[i].step && step < notes[i].step + notes[i].length) return i;
    return -1;
  }

  void changeModTarget(ModLane& lane, int delta) {
    std::lock_guard<std::recursive_mutex> engine(engineMutex);
    if (host.controls().empty()) return;
    lane.control = (lane.control + delta + host.controls().size()) % host.controls().size();
    lane.symbol = host.controls()[lane.control].symbol;
    const auto& c = host.controls()[lane.control];
    float n = (host.controlValue(lane.control) - c.minimum) / (c.maximum - c.minimum);
    lane.values.fill(n); lane.enabled = true; savePattern();
  }

  void syncMods() {
    for (auto& lane : mods) {
      lane.control = lane.symbol.empty() ? -1 : host.controlBySymbol(lane.symbol);
      if (lane.control < 0 && !host.controls().empty()) changeModTarget(lane, 1);
    }
  }

  void draw() {
    XSetForeground(display, gc, color(0x20242e)); XFillRectangle(display, window, gc, 0, 0, WIDTH, HEIGHT);
    drawButton(10, 12, 44, 28, "<"); drawButton(58, 12, 44, 28, ">");
    drawText(112, 31, plugins.empty() ? "No LV2 instruments" : plugins[pluginIndex].name, 0xffffff);
    drawButton(850, 12, 176, 28, nativeUiVisible ? "Hide plugin GUI" : "Open plugin GUI");
    drawButton(10, 52, 70, 30, playing ? "Pause" : "Play");
    drawButton(86, 52, 70, 30, recording ? "Rec ON" : "Record"); drawButton(162, 52, 70, 30, "Stop");
    drawButton(238, 52, 78, 30, "Export"); drawButton(322, 52, 65, 30, "Clear");
    drawButton(400, 52, 28, 30, "-"); drawText(435, 72, std::to_string(bpm) + " BPM", 0xffffff);
    drawButton(475, 52, 28, 30, "+");
    drawButton(520, 52, 118, 30, view == 0 ? "Notes" : "Mod " + std::to_string(view));
    drawText(655, 72, "Keys: A W S E D F T G Y H U J K O L P", 0xaeb7c8);
    if (view == 0) drawPiano(); else drawMod();
    if (controlPicker) drawControlPicker();
    drawText(12, 678, status, 0xc8d0dd);
    XFlush(display);
  }

  void drawPiano() {
    const int cw = GRID_W / STEPS, rh = GRID_H / PITCHES;
    for (int row = 0; row < PITCHES; ++row) {
      int pitch = BASE_NOTE + PITCHES - 1 - row;
      bool black = isBlack(pitch);
      XSetForeground(display, gc, color(black ? 0x2b303b : 0x353b48));
      XFillRectangle(display, window, gc, GRID_X, GRID_Y + row * rh, GRID_W, rh);
      drawText(8, GRID_Y + row * rh + rh - 3, noteName(pitch), black ? 0xaeb7c8 : 0xffffff);
    }
    XSetForeground(display, gc, color(0x4b5363));
    for (int i = 0; i <= STEPS; ++i) {
      if (i % 4 == 0) XSetForeground(display, gc, color(0x768099)); else XSetForeground(display, gc, color(0x454b58));
      int x = GRID_X + i * cw; XDrawLine(display, window, gc, x, GRID_Y, x, GRID_Y + GRID_H);
    }
    for (int i = 0; i <= PITCHES; ++i) {
      int y = GRID_Y + i * rh; XDrawLine(display, window, gc, GRID_X, y, GRID_X + GRID_W, y);
    }
    for (size_t i = 0; i < notes.size(); ++i) {
      const auto& note = notes[i];
      int row = BASE_NOTE + PITCHES - 1 - note.pitch;
      int x = GRID_X + note.step * cw + 1, y = GRID_Y + row * rh + 1;
      XSetForeground(display, gc, color(static_cast<int>(i) == selectedNote ? 0xffc857 : 0x59c3c3));
      XFillRectangle(display, window, gc, x, y, std::max(3, note.length * cw - 2), rh - 2);
    }
    uint64_t pf = patternFrames();
    if (playing && pf) {
      int x = GRID_X + static_cast<int>((static_cast<double>(playFrame) / pf) * GRID_W);
      XSetForeground(display, gc, color(0xff5b5b)); XDrawLine(display, window, gc, x, GRID_Y, x, GRID_Y + GRID_H);
    }
    drawText(112, 625, "Drag to set note length. Right-click deletes. Delete key removes selected note.", 0xaeb7c8);
  }

  void drawMod() {
    ModLane& lane = mods[view - 1];
    drawButton(10, 106, 40, 28, "<"); drawButton(54, 106, 40, 28, ">");
    std::string target = lane.control >= 0 && lane.control < static_cast<int>(host.controls().size())
      ? host.controls()[lane.control].name : "No numeric controls";
    drawText(104, 125, target, 0xffffff);
    drawButton(710, 106, 74, 28, lane.enabled ? "Enabled" : "Disabled");
    drawButton(790, 106, 70, 28, waveName(lane.wave));
    drawButton(866, 106, 34, 28, "R-"); drawButton(904, 106, 34, 28, "R+");
    drawButton(942, 106, 34, 28, "D-"); drawButton(980, 106, 34, 28, "D+");
    drawText(710, 95, "LFO rate " + number(lane.rate) + " depth " + number(lane.depth), 0xaeb7c8);
    XSetForeground(display, gc, color(0x303642)); XFillRectangle(display, window, gc, GRID_X, GRID_Y, GRID_W, GRID_H);
    const int cw = GRID_W / STEPS;
    XSetForeground(display, gc, color(0x4b5363));
    for (int i = 0; i <= STEPS; ++i) {
      int x = GRID_X + i * cw; XDrawLine(display, window, gc, x, GRID_Y, x, GRID_Y + GRID_H);
    }
    for (int i = 0; i <= 4; ++i) {
      int y = GRID_Y + i * GRID_H / 4; XDrawLine(display, window, gc, GRID_X, y, GRID_X + GRID_W, y);
      drawText(78, y + 4, number(1.0f - i / 4.0f), 0xaeb7c8);
    }
    XSetForeground(display, gc, color(0x7c5cff));
    for (int i = 0; i < STEPS; ++i) {
      int x = GRID_X + i * cw + 2;
      int h = static_cast<int>(lane.values[i] * (GRID_H - 2));
      XFillRectangle(display, window, gc, x, GRID_Y + GRID_H - h, cw - 3, h);
    }
    drawText(112, 625, "Draw step values. LFO is added around the automation curve.", 0xaeb7c8);
  }

  static constexpr int PICKER_ROWS = 18;
  void drawControlPicker() {
    const int x = 190, y = 105, w = 660, h = 500;
    XSetForeground(display, gc, color(0x11141b)); XFillRectangle(display, window, gc, x, y, w, h);
    XSetForeground(display, gc, color(0x7c86a0)); XDrawRectangle(display, window, gc, x, y, w, h);
    drawText(x + 18, y + 28, "Choose an LV2 control", 0xffffff);
    drawButton(x + w - 122, y + 10, 46, 26, "Prev");
    drawButton(x + w - 68, y + 10, 46, 26, "Next");
    const auto& controls = host.controls();
    int start = pickerPage * PICKER_ROWS;
    for (int row = 0; row < PICKER_ROWS; ++row) {
      int index = start + row;
      if (index >= static_cast<int>(controls.size())) break;
      int ry = y + 48 + row * 24;
      if (view > 0 && mods[view - 1].control == index) {
        XSetForeground(display, gc, color(0x41495d)); XFillRectangle(display, window, gc, x + 12, ry - 16, w - 24, 22);
      }
      drawText(x + 20, ry, controls[index].name, 0xdce2ee);
      drawText(x + 400, ry, controls[index].symbol, 0x8f9ab0);
    }
    drawText(x + 18, y + h - 15, "Click a control. Right-click outside this box to cancel.", 0xaeb7c8);
  }

  void pickerMouseDown(const XButtonEvent& e) {
    const int x = 190, y = 105, w = 660, h = 500;
    const int pages = std::max(1, (static_cast<int>(host.controls().size()) + PICKER_ROWS - 1) / PICKER_ROWS);
    if (e.button == Button3 || e.x < x || e.x >= x + w || e.y < y || e.y >= y + h) {
      controlPicker = false; redraw(); return;
    }
    if (buttonHit(e.x, e.y, x + w - 122, y + 10, 46, 26)) { pickerPage = (pickerPage + pages - 1) % pages; redraw(); return; }
    if (buttonHit(e.x, e.y, x + w - 68, y + 10, 46, 26)) { pickerPage = (pickerPage + 1) % pages; redraw(); return; }
    int row = (e.y - (y + 32)) / 24;
    int index = pickerPage * PICKER_ROWS + row;
    if (row >= 0 && row < PICKER_ROWS && index >= 0 && index < static_cast<int>(host.controls().size())) {
      ModLane& lane = mods[view - 1];
      lane.control = index; lane.symbol = host.controls()[index].symbol; lane.enabled = true;
      const auto& c = host.controls()[index];
      float n = (host.controlValue(index) - c.minimum) / (c.maximum - c.minimum);
      lane.values.fill(n); controlPicker = false; savePattern(); redraw();
    }
  }

  void drawButton(int x, int y, int w, int h, const std::string& label) {
    XSetForeground(display, gc, color(0x41495d)); XFillRectangle(display, window, gc, x, y, w, h);
    XSetForeground(display, gc, color(0x7c86a0)); XDrawRectangle(display, window, gc, x, y, w, h);
    drawText(x + 7, y + h / 2 + 5, label, 0xffffff);
  }

  void drawText(int x, int y, const std::string& text, uint32_t rgb) {
    XSetForeground(display, gc, color(rgb)); XDrawString(display, window, gc, x, y, text.c_str(), text.size());
  }

  void redraw() { if (display && window) { XClearArea(display, window, 0, 0, 0, 0, True); } }
  static bool isBlack(int midi) { int n = midi % 12; return n == 1 || n == 3 || n == 6 || n == 8 || n == 10; }
  static std::string noteName(int midi) {
    static const char* names[] = {"C","C#","D","D#","E","F","F#","G","G#","A","A#","B"};
    return std::string(names[midi % 12]) + std::to_string(midi / 12 - 1);
  }
  static std::string waveName(LfoWave wave) {
    static const char* names[] = {"Sine", "Triangle", "Square", "Saw"}; return names[static_cast<int>(wave)];
  }
  static std::string number(float value) { char b[24]; std::snprintf(b, sizeof(b), "%.2f", value); return b; }

  void savePattern() {
    if (plugins.empty()) return;
    std::ofstream out(configDir / "pattern.txt");
    if (!out) return;
    out << "plugin " << plugins[pluginIndex].uri << "\n" << "bpm " << bpm << "\n";
    for (const auto& note : notes) out << "note " << note.step << ' ' << note.pitch << ' ' << note.length << ' ' << note.velocity << "\n";
    {
      std::lock_guard<std::recursive_mutex> engine(engineMutex);
      for (size_t i = 0; i < host.controls().size(); ++i)
        out << "control " << host.controls()[i].symbol << ' ' << host.controlValue(i) << "\n";
    }
    for (int m = 0; m < MOD_SLOTS; ++m) {
      const auto& lane = mods[m];
      out << "mod " << m << ' ' << (lane.symbol.empty() ? "-" : lane.symbol) << ' ' << lane.enabled << ' '
          << lane.rate << ' ' << lane.depth << ' ' << static_cast<int>(lane.wave);
      for (float value : lane.values) out << ' ' << value;
      out << "\n";
    }
  }

  void loadPattern() {
    std::ifstream in(configDir / "pattern.txt");
    std::string pluginUri;
    std::map<std::string, float> savedControls;
    if (in) {
      std::string line;
      while (std::getline(in, line)) {
        std::istringstream row(line); std::string type; row >> type;
        if (type == "plugin") row >> pluginUri;
        else if (type == "bpm") row >> bpm;
        else if (type == "note") { Note n; row >> n.step >> n.pitch >> n.length >> n.velocity; notes.push_back(n); }
        else if (type == "control") { std::string symbol; float value; row >> symbol >> value; savedControls[symbol] = value; }
        else if (type == "mod") {
          int slot, enabled, wave; std::string symbol; row >> slot >> symbol >> enabled;
          if (slot >= 0 && slot < MOD_SLOTS) {
            auto& lane = mods[slot]; lane.symbol = symbol == "-" ? "" : symbol; lane.enabled = enabled;
            row >> lane.rate >> lane.depth >> wave; lane.wave = static_cast<LfoWave>(std::clamp(wave, 0, 3));
            for (float& value : lane.values) row >> value;
          }
        }
      }
    }
    pluginIndex = 0;
    for (size_t i = 0; i < plugins.size(); ++i) if (plugins[i].uri == pluginUri) pluginIndex = i;
    if (!plugins.empty() && loadPlugin(pluginIndex)) {
      for (const auto& [symbol, value] : savedControls) { int c = host.controlBySymbol(symbol); if (c >= 0) host.setControl(c, value); }
      syncMods();
    }
  }

  LilvWorld* world = nullptr;
  Urids urids;
  Lv2Host host;
  std::vector<PluginEntry> plugins;
  int pluginIndex = 0;
  std::vector<Note> notes;
  std::array<ModLane, MOD_SLOTS> mods;
  int bpm = 120;
  float defaultVelocity = 0.8f;
  int defaultLength = 1;
  int selectedNote = -1;
  int view = 0;
  bool dragging = false;
  bool controlPicker = false;
  int pickerPage = 0;
  int dragStart = 0;
  std::array<bool, 128> held{};
  std::atomic<bool> quit{false};
  std::atomic<bool> playing{false};
  std::atomic<bool> recording{false};
  std::atomic<uint64_t> playFrame{0};
  std::recursive_mutex engineMutex;
  std::recursive_mutex stateMutex;
  std::vector<MidiEvent> pendingMidi;
  std::thread audioThread;
  fs::path configDir;
  std::string status = "Ready";
  Display* display = nullptr;
  int screen = 0;
  Window window = 0;
  GC gc = nullptr;
  XFontStruct* font = nullptr;
  Atom wmDelete = 0;
  std::unordered_map<uint32_t, unsigned long> colorCache;
  SuilHost* uiHost = nullptr;
  SuilInstance* nativeUi = nullptr;
  const LV2UI_Idle_Interface* nativeIdle = nullptr;
  Window nativeUiWindow = 0;
  Window nativeUiChild = 0;
  bool nativeUiVisible = false;
  LV2UI_Resize nativeResize{};
  LV2_Feature nativeParentFeature{};
  LV2_Feature nativeInstanceFeature{};
  LV2_Feature nativeMapFeature{};
  LV2_Feature nativeUnmapFeature{};
  LV2_Feature nativeResizeFeature{};
  std::chrono::steady_clock::time_point lastUiSync{};
};

int main(int argc, char** argv) {
  suil_init(&argc, &argv, SUIL_ARG_NONE);
  App app;
  return app.run();
}
