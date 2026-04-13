"""Simple audio segment selection for voice cloning samples."""

from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import soundfile as sf
from loguru import logger


class WAVSizeCalculator:
    """Calculate WAV file size from audio properties."""

    # WAV header size (44 bytes)
    WAV_HEADER_SIZE = 44

    @staticmethod
    def calculate_size_mb(
        duration_seconds: float,
        sample_rate: int = 44100,
        bit_depth: int = 16,
        channels: int = 1,
    ) -> float:
        """Calculate expected WAV file size in MB.

        Formula: size = header + (sample_rate × bit_depth/8 × channels × duration)

        Args:
            duration_seconds: Audio duration in seconds
            sample_rate: Sample rate in Hz (default: 44100)
            bit_depth: Bit depth (default: 16)
            channels: Number of channels (default: 1 for mono)

        Returns:
            File size in megabytes
        """
        bytes_per_sample = bit_depth // 8
        data_size_bytes = sample_rate * bytes_per_sample * channels * duration_seconds
        total_size_bytes = WAVSizeCalculator.WAV_HEADER_SIZE + data_size_bytes
        return total_size_bytes / (1024 * 1024)

    @staticmethod
    def calculate_max_duration(
        max_size_mb: float = 9.0,
        sample_rate: int = 44100,
        bit_depth: int = 16,
        channels: int = 1,
    ) -> float:
        """Calculate maximum duration that fits within size limit.

        Args:
            max_size_mb: Maximum file size in MB (default: 9.0)
            sample_rate: Sample rate in Hz (default: 44100)
            bit_depth: Bit depth (default: 16)
            channels: Number of channels (default: 1 for mono)

        Returns:
            Maximum duration in seconds

        Raises:
            ValueError: If max_size_mb is too small or parameters are invalid
        """
        # Validate inputs
        if max_size_mb <= 0:
            raise ValueError(f"max_size_mb must be positive, got: {max_size_mb}")

        max_size_bytes = max_size_mb * 1024 * 1024

        # Check if file size can even fit WAV header
        if max_size_bytes <= WAVSizeCalculator.WAV_HEADER_SIZE:
            raise ValueError(
                f"max_size_mb too small ({max_size_mb}MB). "
                f"Minimum required: {(WAVSizeCalculator.WAV_HEADER_SIZE / (1024 * 1024)):.6f}MB"
            )

        if sample_rate <= 0 or bit_depth <= 0 or channels <= 0:
            raise ValueError(
                f"Invalid audio parameters: sample_rate={sample_rate}, "
                f"bit_depth={bit_depth}, channels={channels}"
            )

        data_size_bytes = max_size_bytes - WAVSizeCalculator.WAV_HEADER_SIZE
        bytes_per_sample = bit_depth // 8
        max_duration = data_size_bytes / (sample_rate * bytes_per_sample * channels)

        if max_duration <= 0:
            raise ValueError(f"Calculated max_duration is non-positive: {max_duration}")

        return max_duration


class SegmentSelector:
    """Select optimal segments from audio files for voice cloning."""

    def __init__(
        self,
        target_duration: float = 60.0,
        max_segments: int = 3,
        max_file_size_mb: float = 9.0,
        sample_rate: int = 44100,
        bit_depth: int = 16,
        channels: int = 1,
    ):
        """Initialize segment selector.

        Args:
            target_duration: Target duration in seconds (default: 60)
            max_segments: Maximum number of segments to extract (default: 3)
            max_file_size_mb: Maximum file size in MB (default: 9.0 for ElevenLabs)
            sample_rate: Output sample rate (default: 44100)
            bit_depth: Output bit depth (default: 16)
            channels: Output channels (default: 1 for mono)
        """
        self.max_file_size_mb = max_file_size_mb
        self.sample_rate = sample_rate
        self.bit_depth = bit_depth
        self.channels = channels

        # Calculate maximum duration that fits within file size limit
        self.max_duration = WAVSizeCalculator.calculate_max_duration(
            max_size_mb=max_file_size_mb,
            sample_rate=sample_rate,
            bit_depth=bit_depth,
            channels=channels,
        )

        # OPTIMIZE FOR QUALITY: Use max_duration to fill the 9MB limit
        # Don't artificially cap at 60s - use the full 9MB capacity (~107s for 44.1kHz/16bit/mono)
        if target_duration is None or target_duration > self.max_duration:
            self.target_duration = self.max_duration
        else:
            # Only use custom target_duration if explicitly specified and smaller
            self.target_duration = target_duration

        logger.info(
            f"SegmentSelector initialized: target_duration={self.target_duration:.1f}s "
            f"(max {self.max_duration:.1f}s for {max_file_size_mb}MB limit), "
            f"audio_spec={sample_rate}Hz/{bit_depth}bit/{channels}ch"
        )

        self.max_segments = max_segments
        self.min_segment_duration = 30.0  # Minimum acceptable segment
        self.min_spacing = 30.0  # Minimum spacing between segments (seconds)

    def select_best_segment(self, audio_path: str, output_path: str) -> Dict[str, Any]:
        """Select and extract the best segment from audio file.

        Args:
            audio_path: Path to input audio file
            output_path: Path to save selected segment

        Returns:
            Dictionary with selection results
        """
        logger.info(f"Analyzing audio for best {self.target_duration}s segment: {audio_path}")

        try:
            # Load audio file
            audio, sample_rate = sf.read(audio_path)
            duration = len(audio) / sample_rate

            logger.info(f"Audio duration: {duration:.1f}s, target: {self.target_duration}s")

            # If audio is already shorter than or close to target duration, use it all
            if duration <= self.target_duration + 5.0:  # 5 second tolerance
                logger.info("Audio is already close to target duration, using full audio")
                return self._save_segment(
                    audio,
                    sample_rate,
                    output_path,
                    0,
                    duration,
                    {"method": "full_audio", "reason": "Audio shorter than target duration"},
                )

            # Find the best segment
            best_segment = self._analyze_segments(audio, sample_rate)

            # Extract the selected segment
            start_sample = int(best_segment["start_time"] * sample_rate)
            end_sample = int(best_segment["end_time"] * sample_rate)
            selected_audio = audio[start_sample:end_sample]

            # Save the selected segment
            result = self._save_segment(
                selected_audio,
                sample_rate,
                output_path,
                best_segment["start_time"],
                best_segment["end_time"],
                best_segment,
            )

            logger.success(
                f"Selected best segment: {best_segment['start_time']:.1f}s - {best_segment['end_time']:.1f}s"
            )
            return result

        except Exception as e:
            logger.error(f"Segment selection failed: {e}")
            return {"success": False, "error": str(e), "method": "segment_selection"}

    def select_multiple_segments(
        self, audio_path: str, output_dir: str, max_segments: Optional[int] = None
    ) -> Dict[str, Any]:
        """Select and extract multiple segments from audio file.

        Args:
            audio_path: Path to input audio file
            output_dir: Directory to save selected segments
            max_segments: Override default max_segments

        Returns:
            Dictionary with selection results for all segments
        """
        if max_segments is None:
            max_segments = self.max_segments

        logger.info(
            f"Analyzing audio for best {max_segments} x {self.target_duration}s segments: {audio_path}"
        )

        try:
            # Load audio file
            audio, sample_rate = sf.read(audio_path)
            duration = len(audio) / sample_rate

            logger.info(
                f"Audio duration: {duration:.1f}s, target: {max_segments} x {self.target_duration}s"
            )

            # Check if we have enough audio for multiple segments
            min_duration_needed = self.target_duration + (max_segments - 1) * self.min_spacing
            if duration < min_duration_needed:
                # Not enough audio for multiple segments, fall back to single segment
                logger.info(
                    f"Audio too short for {max_segments} segments, selecting single best segment"
                )
                base_name = Path(audio_path).stem
                single_output = Path(output_dir) / f"{base_name}_segment_1.wav"
                return self.select_best_segment(audio_path, str(single_output))

            # Find multiple segments
            selected_segments = self._analyze_multiple_segments(audio, sample_rate, max_segments)

            # Save all selected segments
            output_results = []
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            base_name = Path(audio_path).stem

            for i, segment in enumerate(selected_segments):
                segment_num = i + 1
                output_path = Path(output_dir) / f"{base_name}_segment_{segment_num}.wav"

                # Extract the selected segment
                start_sample = int(segment["start_time"] * sample_rate)
                end_sample = int(segment["end_time"] * sample_rate)
                selected_audio = audio[start_sample:end_sample]

                # Save the segment
                result = self._save_segment(
                    selected_audio,
                    sample_rate,
                    str(output_path),
                    segment["start_time"],
                    segment["end_time"],
                    segment,
                )

                if result.get("success"):
                    output_results.append(result)
                    logger.success(
                        f"Segment {segment_num}: {segment['start_time']:.1f}s - {segment['end_time']:.1f}s (quality: {segment['quality_score']:.2f})"
                    )

            return {
                "success": True,
                "segments_count": len(output_results),
                "segments": output_results,
                "method": "multiple_segment_selection",
                "total_duration": sum(r["duration"] for r in output_results),
                "average_quality": (
                    sum(r["quality_score"] for r in output_results) / len(output_results)
                    if output_results
                    else 0
                ),
                "output_directory": output_dir,
            }

        except Exception as e:
            logger.error(f"Multiple segment selection failed: {e}")
            return {"success": False, "error": str(e), "method": "multiple_segment_selection"}

    def _analyze_segments(self, audio: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """Analyze audio to find the best segment.

        Args:
            audio: Audio data
            sample_rate: Sample rate

        Returns:
            Best segment information
        """
        duration = len(audio) / sample_rate
        segment_samples = int(self.target_duration * sample_rate)

        # Create analysis windows
        step_size = int(5.0 * sample_rate)  # Analyze every 5 seconds
        segments = []

        for start_sample in range(0, len(audio) - segment_samples + 1, step_size):
            end_sample = start_sample + segment_samples
            start_time = start_sample / sample_rate
            end_time = end_sample / sample_rate

            # Skip segments that go beyond the audio
            if end_sample > len(audio):
                continue

            segment_audio = audio[start_sample:end_sample]

            # Analyze this segment
            quality_score = self._calculate_segment_quality(segment_audio, sample_rate)

            segments.append(
                {
                    "start_time": start_time,
                    "end_time": end_time,
                    "start_sample": start_sample,
                    "end_sample": end_sample,
                    "quality_score": quality_score,
                    "duration": end_time - start_time,
                }
            )

        # Sort by quality score (highest first)
        segments.sort(key=lambda x: x["quality_score"], reverse=True)

        if not segments:
            # Fallback: use the middle portion
            start_time = max(0, (duration - self.target_duration) / 2)
            end_time = min(duration, start_time + self.target_duration)
            return {
                "start_time": start_time,
                "end_time": end_time,
                "quality_score": 0.5,
                "method": "fallback_middle",
                "reason": "No segments found, using middle portion",
            }

        best_segment = segments[0]
        best_segment["method"] = "quality_analysis"
        best_segment["total_segments_analyzed"] = len(segments)

        return best_segment

    def _analyze_multiple_segments(
        self, audio: np.ndarray, sample_rate: int, max_segments: int
    ) -> List[Dict[str, Any]]:
        """Analyze audio to find multiple diverse segments.

        Args:
            audio: Audio data
            sample_rate: Sample rate
            max_segments: Maximum number of segments to select

        Returns:
            List of selected segments
        """
        duration = len(audio) / sample_rate
        segment_samples = int(self.target_duration * sample_rate)

        # Create analysis windows
        step_size = int(10.0 * sample_rate)  # Analyze every 10 seconds
        all_segments = []

        for start_sample in range(0, len(audio) - segment_samples + 1, step_size):
            end_sample = start_sample + segment_samples
            start_time = start_sample / sample_rate
            end_time = end_sample / sample_rate

            # Skip segments that go beyond the audio
            if end_sample > len(audio):
                continue

            segment_audio = audio[start_sample:end_sample]

            # Analyze this segment
            quality_score = self._calculate_segment_quality(segment_audio, sample_rate)

            all_segments.append(
                {
                    "start_time": start_time,
                    "end_time": end_time,
                    "start_sample": start_sample,
                    "end_sample": end_sample,
                    "quality_score": quality_score,
                    "duration": end_time - start_time,
                }
            )

        # Sort by quality score (highest first)
        all_segments.sort(key=lambda x: x["quality_score"], reverse=True)

        if not all_segments:
            # Fallback: create single segment from middle
            start_time = max(0, (duration - self.target_duration) / 2)
            end_time = min(duration, start_time + self.target_duration)
            return [
                {
                    "start_time": start_time,
                    "end_time": end_time,
                    "quality_score": 0.5,
                    "duration": end_time - start_time,
                    "method": "fallback_middle",
                }
            ]

        # Select diverse segments with minimum spacing
        selected_segments = []
        min_spacing_samples = int(self.min_spacing * sample_rate)

        for segment in all_segments:
            if len(selected_segments) >= max_segments:
                break

            # Check if this segment conflicts with already selected segments
            conflicts = False
            for selected in selected_segments:
                # Check for overlap or insufficient spacing
                gap_start = max(segment["start_sample"], selected["start_sample"])
                gap_end = min(segment["end_sample"], selected["end_sample"])

                if (
                    gap_end > gap_start
                    or abs(segment["start_sample"] - selected["end_sample"])  # Overlapping
                    < min_spacing_samples
                    or abs(selected["start_sample"] - segment["end_sample"])  # Too close after
                    < min_spacing_samples
                ):  # Too close before
                    conflicts = True
                    break

            if not conflicts:
                segment["method"] = "quality_analysis_diverse"
                segment["segment_number"] = len(selected_segments) + 1
                selected_segments.append(segment)

        # Sort selected segments by start time for logical ordering
        selected_segments.sort(key=lambda x: x["start_time"])

        logger.info(
            f"Selected {len(selected_segments)} diverse segments from {len(all_segments)} candidates"
        )
        return selected_segments

    def _calculate_segment_quality(self, audio: np.ndarray, sample_rate: int) -> float:
        """Calculate quality score for an audio segment.

        Args:
            audio: Audio segment
            sample_rate: Sample rate

        Returns:
            Quality score (0.0 to 1.0, higher is better)
        """
        quality_factors = []

        try:
            # 1. RMS Energy (consistent speech level)
            rms = np.sqrt(np.mean(audio**2))
            # Normalize RMS to 0-1 range (good speech is typically 0.01-0.1)
            rms_score = min(1.0, max(0.0, (rms - 0.005) / 0.1))
            quality_factors.append(("rms", rms_score, 0.4))

            # 2. Zero Crossing Rate (speech activity)
            zero_crossings = np.where(np.diff(np.signbit(audio)))[0]
            zcr = len(zero_crossings) / len(audio)
            # Good speech typically has ZCR around 0.05-0.15
            zcr_score = 1.0 - abs(zcr - 0.1) / 0.1
            zcr_score = max(0.0, min(1.0, zcr_score))
            quality_factors.append(("zcr", zcr_score, 0.3))

            # 3. Silence ratio (minimize silence)
            silence_threshold = 0.05 * np.max(np.abs(audio))
            silence_frames = np.sum(np.abs(audio) < silence_threshold)
            silence_ratio = silence_frames / len(audio)
            silence_score = 1.0 - silence_ratio  # Lower silence is better
            quality_factors.append(("silence", silence_score, 0.3))

        except Exception as e:
            logger.warning(f"Error calculating quality factors: {e}")
            return 0.5  # Default middle score

        # Calculate weighted average
        total_score = 0.0
        total_weight = 0.0

        for name, score, weight in quality_factors:
            total_score += score * weight
            total_weight += weight

        final_score = total_score / total_weight if total_weight > 0 else 0.5
        return max(0.0, min(1.0, final_score))

    def _save_segment(
        self,
        audio: np.ndarray,
        sample_rate: int,
        output_path: str,
        start_time: float,
        end_time: float,
        metadata: Dict,
    ) -> Dict[str, Any]:
        """Save selected audio segment to file with size validation.

        Args:
            audio: Audio data to save
            sample_rate: Sample rate
            output_path: Output file path
            start_time: Start time of segment
            end_time: End time of segment
            metadata: Additional metadata

        Returns:
            Save result information
        """
        try:
            duration = end_time - start_time

            # Validate sample rate matches expected output sample rate
            # This ensures accurate size prediction (soundfile doesn't resample automatically)
            if sample_rate != self.sample_rate:
                logger.warning(
                    f"Sample rate mismatch: audio has {sample_rate}Hz, "
                    f"but expected {self.sample_rate}Hz. Size prediction may be inaccurate."
                )
                # Use actual sample_rate for prediction since we're not resampling
                prediction_sample_rate = sample_rate
            else:
                prediction_sample_rate = self.sample_rate

            # Predict file size BEFORE saving
            num_channels = 1 if len(audio.shape) == 1 else audio.shape[1]
            predicted_size_mb = WAVSizeCalculator.calculate_size_mb(
                duration_seconds=duration,
                sample_rate=prediction_sample_rate,
                bit_depth=self.bit_depth,
                channels=num_channels,
            )

            # Validate predicted size
            if predicted_size_mb > self.max_file_size_mb:
                error_msg = (
                    f"Segment would exceed {self.max_file_size_mb}MB limit: "
                    f"predicted {predicted_size_mb:.2f}MB for {duration:.1f}s segment. "
                    f"Max allowed duration: {self.max_duration:.1f}s"
                )
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "output_path": output_path,
                    "predicted_size_mb": predicted_size_mb,
                    "duration": duration,
                }

            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            # Save as WAV for maximum quality
            sf.write(output_path, audio, sample_rate, subtype="PCM_16")

            # Verify actual file size
            actual_size_mb = Path(output_path).stat().st_size / (1024 * 1024)

            # Double-check actual size (should match prediction closely)
            if actual_size_mb > self.max_file_size_mb:
                # This should rarely happen, but if it does, delete the file
                Path(output_path).unlink()
                error_msg = (
                    f"Saved segment exceeds {self.max_file_size_mb}MB limit: "
                    f"{actual_size_mb:.2f}MB (predicted: {predicted_size_mb:.2f}MB). "
                    f"File deleted."
                )
                logger.error(error_msg)
                return {
                    "success": False,
                    "error": error_msg,
                    "output_path": output_path,
                    "predicted_size_mb": predicted_size_mb,
                    "actual_size_mb": actual_size_mb,
                }

            logger.success(
                f"Segment saved: {actual_size_mb:.2f}MB (predicted: {predicted_size_mb:.2f}MB), "
                f"duration: {duration:.1f}s"
            )

            return {
                "success": True,
                "output_path": output_path,
                "start_time": start_time,
                "end_time": end_time,
                "duration": duration,
                "file_size_mb": actual_size_mb,
                "predicted_size_mb": predicted_size_mb,
                "sample_rate": sample_rate,
                "quality_score": metadata.get("quality_score", 0.0),
                "selection_method": metadata.get("method", "unknown"),
                "metadata": metadata,
            }

        except Exception as e:
            logger.error(f"Failed to save segment: {e}")
            return {"success": False, "error": str(e), "output_path": output_path}

    def is_within_file_size_limit(self, file_path: str, limit_mb: float = 10.0) -> bool:
        """Check if file is within size limit.

        Args:
            file_path: Path to file
            limit_mb: Size limit in megabytes

        Returns:
            True if within limit
        """
        try:
            file_size_mb = Path(file_path).stat().st_size / (1024 * 1024)
            return file_size_mb <= limit_mb
        except:
            return False
