$nyquist plug-in
$version 4
$type tool process
$preview disabled
$name "PeteShift"
$author "Jacob Pereira"
$release 2.0.0
$copyright "GNU General Public License v2.0 or later"
$debugbutton false

$control MODE "Stretch mode" choice (("KeepPitch" "Keep pitch")
                                       ("TapeSpeed" "Tape speed (pitch follows speed)")) 0

;; The time selection is the target duration. Unlike a normal process effect,
;; this macro-effect selects the complete source clip before asking Audacity's
;; built-in stretcher to process it. A target selection shorter than the clip
;; therefore compresses the complete clip instead of cutting its tail off.

(defun flatten-clips (clips)
  (if (arrayp clips)
      (let ((result nil))
        (dotimes (channel (length clips) result)
          (setf result (append result (aref clips channel)))))
      clips))

(defun clip-containing-start (clips selection-start selection-end)
  (let ((fallback nil)
        (best-overlap 0))
    (dolist (clip (flatten-clips clips))
      (let* ((clip-start (first clip))
             (clip-end (second clip))
             (overlap (max 0 (- (min clip-end selection-end)
                                (max clip-start selection-start)))))
        (when (and (<= clip-start selection-start)
                   (< selection-start clip-end))
          (return-from clip-containing-start clip))
        (when (> overlap best-overlap)
          (setf best-overlap overlap)
          (setf fallback clip))))
    fallback))

(defun run-peteshift ()
  (let* ((selection-start (get '*selection* 'start))
         (selection-end (get '*selection* 'end))
         (target-duration (- selection-end selection-start))
         (source-clip (clip-containing-start (get '*track* 'clips)
                                             selection-start selection-end)))
    (cond
      ((<= target-duration 0)
        "PeteShift needs a time selection showing the desired output length.")
      ((null source-clip)
        "PeteShift could not find an audio clip under the selection.")
      (t
        (let* ((clip-start (first source-clip))
               (clip-end (second source-clip))
               (source-duration (- clip-end clip-start))
               ;; Audacity's Percentage is a speed/tempo change, not a duration
               ;; percentage: new-duration = old-duration / (1 + p/100).
               (percentage (* 100.0 (- (/ source-duration target-duration) 1.0))))
          (aud-do (format nil
                          "SelectTime: Start=~a End=~a RelativeTo=ProjectStart"
                          clip-start clip-end))
          (if (= MODE 0)
              (aud-do (format nil "ChangeTempo: Percentage=~a SBSMS=0"
                              percentage))
              (aud-do (format nil "ChangeSpeedAndPitch: Percentage=~a"
                              percentage)))
          "")))))

;; Compound tool/process plug-ins can be invoked once per selected track. The
;; Audacity built-in effect already operates on every selected track, so issue
;; the macro commands only for the first track.
(if (= (get '*track* 'index) 1)
    (run-peteshift)
    "")
