CXX ?= c++
CXXFLAGS ?= -O2 -pipe -std=c++17 -Wall -Wextra -Wpedantic
PKGS = lilv-0 suil-0 libpulse-simple x11

all: temporaman-lv2

temporaman-lv2: temporaman-lv2.cpp
	$(CXX) $(CXXFLAGS) $(shell pkg-config --cflags $(PKGS)) -o $@ $< $(shell pkg-config --libs $(PKGS))

clean:
	rm -f temporaman-lv2
