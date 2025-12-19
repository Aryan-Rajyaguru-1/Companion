#!/usr/bin/env python3
"""
Multi-Modal Processing System
==============================

Handles multiple input/output modalities:
- Text (native)
- Images (vision models)
- Audio (speech-to-text, text-to-speech)
- Video (frame extraction + analysis)
- Documents (PDF, DOCX parsing)
"""

import logging
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass
from enum import Enum
import base64
import os
from pathlib import Path

logger = logging.getLogger(__name__)


class ModalityType(Enum):
    """Supported modalities"""
    TEXT = "text"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    DOCUMENT = "document"


@dataclass
class MediaInput:
    """Input media item"""
    type: ModalityType
    content: Union[str, bytes]  # URL, file path, or raw bytes
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class MediaOutput:
    """Processed media output"""
    type: ModalityType
    content: Any  # Processed content
    raw_response: str
    confidence: float
    metadata: Dict[str, Any]


class ImageProcessor:
    """Process images using vision models"""
    
    def __init__(self):
        self.enabled = False
        self._check_dependencies()
        
    def _check_dependencies(self):
        """Check if vision capabilities are available"""
        try:
            # Check for PIL/Pillow
            from PIL import Image
            self.enabled = True
            logger.info("✅ Image processing available")
        except ImportError:
            logger.warning("⚠️  PIL not available. Install: pip install Pillow")
    
    def encode_image_to_base64(self, image_path: str) -> str:
        """Encode image to base64 for API calls"""
        try:
            with open(image_path, 'rb') as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to encode image: {e}")
            return ""
    
    def analyze_image(
        self,
        image_input: Union[str, bytes],
        prompt: str,
        vision_llm_function
    ) -> MediaOutput:
        """
        Analyze image using vision model
        
        Args:
            image_input: Image path, URL, or bytes
            prompt: What to analyze
            vision_llm_function: Function that calls vision model
            
        Returns:
            MediaOutput with analysis
        """
        if not self.enabled:
            return MediaOutput(
                type=ModalityType.IMAGE,
                content=None,
                raw_response="Image processing not available",
                confidence=0.0,
                metadata={"error": "PIL not installed"}
            )
        
        try:
            # Prepare image
            if isinstance(image_input, str):
                if image_input.startswith(('http://', 'https://')):
                    # URL
                    image_data = image_input
                else:
                    # File path
                    image_data = self.encode_image_to_base64(image_input)
            else:
                # Raw bytes
                image_data = base64.b64encode(image_input).decode('utf-8')
            
            # Call vision model
            response = vision_llm_function(prompt, image_data)
            
            return MediaOutput(
                type=ModalityType.IMAGE,
                content=response,
                raw_response=response,
                confidence=0.9,
                metadata={
                    "prompt": prompt,
                    "image_type": "url" if isinstance(image_input, str) and image_input.startswith('http') else "file"
                }
            )
        
        except Exception as e:
            logger.error(f"Image analysis failed: {e}")
            return MediaOutput(
                type=ModalityType.IMAGE,
                content=None,
                raw_response=str(e),
                confidence=0.0,
                metadata={"error": str(e)}
            )
    
    def extract_text_from_image(self, image_input: Union[str, bytes], ocr_function) -> str:
        """Extract text from image using OCR"""
        try:
            # OCR implementation would go here
            # For now, use vision model
            return ocr_function(image_input)
        except Exception as e:
            logger.error(f"OCR failed: {e}")
            return ""


class AudioProcessor:
    """Process audio using speech models"""
    
    def __init__(self):
        self.enabled = False
        self._check_dependencies()
        
    def _check_dependencies(self):
        """Check if audio capabilities are available"""
        # Check for audio libraries
        try:
            import soundfile
            self.enabled = True
            logger.info("✅ Audio processing available")
        except ImportError:
            logger.warning("⚠️  Audio libraries not available. Install: pip install soundfile")
    
    def transcribe_audio(
        self,
        audio_input: Union[str, bytes],
        whisper_function,
        language: Optional[str] = None
    ) -> MediaOutput:
        """
        Transcribe audio to text
        
        Args:
            audio_input: Audio file path, URL, or bytes
            whisper_function: Function that calls Whisper/transcription API
            language: Optional language code
            
        Returns:
            MediaOutput with transcription
        """
        if not self.enabled:
            return MediaOutput(
                type=ModalityType.AUDIO,
                content=None,
                raw_response="Audio processing not available",
                confidence=0.0,
                metadata={"error": "Audio libraries not installed"}
            )
        
        try:
            # Call transcription service
            transcription = whisper_function(audio_input, language)
            
            return MediaOutput(
                type=ModalityType.AUDIO,
                content=transcription,
                raw_response=transcription,
                confidence=0.95,
                metadata={
                    "language": language or "auto",
                    "duration": self._get_audio_duration(audio_input) if isinstance(audio_input, str) else None
                }
            )
        
        except Exception as e:
            logger.error(f"Audio transcription failed: {e}")
            return MediaOutput(
                type=ModalityType.AUDIO,
                content=None,
                raw_response=str(e),
                confidence=0.0,
                metadata={"error": str(e)}
            )
    
    def synthesize_speech(
        self,
        text: str,
        tts_function,
        voice: str = "default"
    ) -> MediaOutput:
        """
        Convert text to speech
        
        Args:
            text: Text to synthesize
            tts_function: Function that calls TTS API
            voice: Voice to use
            
        Returns:
            MediaOutput with audio data
        """
        try:
            audio_data = tts_function(text, voice)
            
            return MediaOutput(
                type=ModalityType.AUDIO,
                content=audio_data,
                raw_response="Audio generated successfully",
                confidence=1.0,
                metadata={"voice": voice, "text_length": len(text)}
            )
        
        except Exception as e:
            logger.error(f"Speech synthesis failed: {e}")
            return MediaOutput(
                type=ModalityType.AUDIO,
                content=None,
                raw_response=str(e),
                confidence=0.0,
                metadata={"error": str(e)}
            )
    
    def _get_audio_duration(self, audio_path: str) -> Optional[float]:
        """Get audio duration in seconds"""
        try:
            import soundfile as sf
            with sf.SoundFile(audio_path) as audio_file:
                return len(audio_file) / audio_file.samplerate
        except:
            return None


class VideoProcessor:
    """Process video files"""
    
    def __init__(self):
        self.enabled = False
        self._check_dependencies()
        
    def _check_dependencies(self):
        """Check if video capabilities are available"""
        try:
            import cv2
            self.enabled = True
            logger.info("✅ Video processing available")
        except ImportError:
            logger.warning("⚠️  OpenCV not available. Install: pip install opencv-python")
    
    def extract_frames(
        self,
        video_path: str,
        frame_rate: int = 1,
        max_frames: int = 10
    ) -> List[bytes]:
        """
        Extract frames from video
        
        Args:
            video_path: Path to video file
            frame_rate: Extract 1 frame per N seconds
            max_frames: Maximum frames to extract
            
        Returns:
            List of frame images as bytes
        """
        if not self.enabled:
            return []
        
        try:
            import cv2
            import io
            from PIL import Image
            
            frames = []
            cap = cv2.VideoCapture(video_path)
            fps = cap.get(cv2.CAP_PROP_FPS)
            frame_interval = int(fps * frame_rate)
            
            frame_count = 0
            while len(frames) < max_frames:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_count % frame_interval == 0:
                    # Convert BGR to RGB
                    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    img = Image.fromarray(frame_rgb)
                    
                    # Convert to bytes
                    img_bytes = io.BytesIO()
                    img.save(img_bytes, format='JPEG')
                    frames.append(img_bytes.getvalue())
                
                frame_count += 1
            
            cap.release()
            return frames
        
        except Exception as e:
            logger.error(f"Frame extraction failed: {e}")
            return []
    
    def analyze_video(
        self,
        video_path: str,
        prompt: str,
        vision_llm_function,
        frame_rate: int = 1
    ) -> MediaOutput:
        """
        Analyze video by processing frames
        
        Args:
            video_path: Path to video
            prompt: What to analyze
            vision_llm_function: Function for vision analysis
            frame_rate: Frames per second to analyze
            
        Returns:
            MediaOutput with video analysis
        """
        try:
            # Extract frames
            frames = self.extract_frames(video_path, frame_rate)
            
            if not frames:
                return MediaOutput(
                    type=ModalityType.VIDEO,
                    content=None,
                    raw_response="Failed to extract frames",
                    confidence=0.0,
                    metadata={"error": "Frame extraction failed"}
                )
            
            # Analyze each frame
            analyses = []
            for i, frame in enumerate(frames):
                analysis = vision_llm_function(f"Frame {i+1}: {prompt}", frame)
                analyses.append(analysis)
            
            # Combine analyses
            combined_analysis = f"Video analysis ({len(frames)} frames):\n" + "\n".join(
                f"Frame {i+1}: {analysis}" for i, analysis in enumerate(analyses)
            )
            
            return MediaOutput(
                type=ModalityType.VIDEO,
                content=combined_analysis,
                raw_response=combined_analysis,
                confidence=0.85,
                metadata={
                    "frames_analyzed": len(frames),
                    "frame_rate": frame_rate,
                    "prompt": prompt
                }
            )
        
        except Exception as e:
            logger.error(f"Video analysis failed: {e}")
            return MediaOutput(
                type=ModalityType.VIDEO,
                content=None,
                raw_response=str(e),
                confidence=0.0,
                metadata={"error": str(e)}
            )


class DocumentProcessor:
    """Process documents (PDF, DOCX, etc.)"""
    
    def __init__(self):
        self.enabled = False
        self._check_dependencies()
        
    def _check_dependencies(self):
        """Check if document processing is available"""
        try:
            import PyPDF2
            self.enabled = True
            logger.info("✅ Document processing available")
        except ImportError:
            logger.warning("⚠️  PyPDF2 not available. Install: pip install PyPDF2")
    
    def extract_text_from_pdf(self, pdf_path: str) -> str:
        """Extract text from PDF"""
        if not self.enabled:
            return ""
        
        try:
            import PyPDF2
            
            text = ""
            with open(pdf_path, 'rb') as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            
            return text.strip()
        
        except Exception as e:
            logger.error(f"PDF extraction failed: {e}")
            return ""
    
    def extract_text_from_docx(self, docx_path: str) -> str:
        """Extract text from DOCX"""
        try:
            import docx
            doc = docx.Document(docx_path)
            return "\n".join([paragraph.text for paragraph in doc.paragraphs])
        except ImportError:
            logger.warning("python-docx not available")
            return ""
        except Exception as e:
            logger.error(f"DOCX extraction failed: {e}")
            return ""
    
    def process_document(self, doc_path: str) -> MediaOutput:
        """
        Process document and extract content
        
        Args:
            doc_path: Path to document
            
        Returns:
            MediaOutput with extracted text
        """
        try:
            ext = Path(doc_path).suffix.lower()
            
            if ext == '.pdf':
                text = self.extract_text_from_pdf(doc_path)
            elif ext in ['.docx', '.doc']:
                text = self.extract_text_from_docx(doc_path)
            elif ext in ['.txt', '.md']:
                with open(doc_path, 'r', encoding='utf-8') as f:
                    text = f.read()
            else:
                return MediaOutput(
                    type=ModalityType.DOCUMENT,
                    content=None,
                    raw_response=f"Unsupported document type: {ext}",
                    confidence=0.0,
                    metadata={"error": f"Unsupported type: {ext}"}
                )
            
            return MediaOutput(
                type=ModalityType.DOCUMENT,
                content=text,
                raw_response=text,
                confidence=1.0 if text else 0.0,
                metadata={
                    "file_type": ext,
                    "char_count": len(text),
                    "word_count": len(text.split())
                }
            )
        
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            return MediaOutput(
                type=ModalityType.DOCUMENT,
                content=None,
                raw_response=str(e),
                confidence=0.0,
                metadata={"error": str(e)}
            )


class MultiModalSystem:
    """
    Unified Multi-Modal Processing System
    Handles all modalities in one place
    """
    
    def __init__(self):
        self.image = ImageProcessor()
        self.audio = AudioProcessor()
        self.video = VideoProcessor()
        self.document = DocumentProcessor()
        
        self.enabled = True
        logger.info("✅ Multi-Modal System initialized")
    
    def process(
        self,
        inputs: List[MediaInput],
        prompt: str,
        llm_function,
        vision_llm_function=None,
        whisper_function=None,
        tts_function=None
    ) -> List[MediaOutput]:
        """
        Process multiple media inputs
        
        Args:
            inputs: List of media inputs
            prompt: Analysis prompt
            llm_function: Standard LLM function
            vision_llm_function: Vision model function
            whisper_function: Speech-to-text function
            tts_function: Text-to-speech function
            
        Returns:
            List of processed outputs
        """
        outputs = []
        
        for media_input in inputs:
            try:
                if media_input.type == ModalityType.IMAGE:
                    if vision_llm_function:
                        output = self.image.analyze_image(
                            media_input.content,
                            prompt,
                            vision_llm_function
                        )
                    else:
                        output = MediaOutput(
                            type=ModalityType.IMAGE,
                            content=None,
                            raw_response="Vision model not available",
                            confidence=0.0,
                            metadata={"error": "No vision function"}
                        )
                
                elif media_input.type == ModalityType.AUDIO:
                    if whisper_function:
                        output = self.audio.transcribe_audio(
                            media_input.content,
                            whisper_function
                        )
                    else:
                        output = MediaOutput(
                            type=ModalityType.AUDIO,
                            content=None,
                            raw_response="Whisper not available",
                            confidence=0.0,
                            metadata={"error": "No whisper function"}
                        )
                
                elif media_input.type == ModalityType.VIDEO:
                    if vision_llm_function:
                        output = self.video.analyze_video(
                            media_input.content,
                            prompt,
                            vision_llm_function
                        )
                    else:
                        output = MediaOutput(
                            type=ModalityType.VIDEO,
                            content=None,
                            raw_response="Vision model not available",
                            confidence=0.0,
                            metadata={"error": "No vision function"}
                        )
                
                elif media_input.type == ModalityType.DOCUMENT:
                    output = self.document.process_document(media_input.content)
                
                else:  # TEXT
                    output = MediaOutput(
                        type=ModalityType.TEXT,
                        content=media_input.content,
                        raw_response=media_input.content,
                        confidence=1.0,
                        metadata={}
                    )
                
                outputs.append(output)
            
            except Exception as e:
                logger.error(f"Failed to process {media_input.type}: {e}")
                outputs.append(MediaOutput(
                    type=media_input.type,
                    content=None,
                    raw_response=str(e),
                    confidence=0.0,
                    metadata={"error": str(e)}
                ))
        
        return outputs
    
    def get_capabilities(self) -> Dict[str, bool]:
        """Get available capabilities"""
        return {
            "image": self.image.enabled,
            "audio": self.audio.enabled,
            "video": self.video.enabled,
            "document": self.document.enabled
        }


# Convenience function
def create_multimodal_system() -> MultiModalSystem:
    """Create and return multi-modal system"""
    return MultiModalSystem()
