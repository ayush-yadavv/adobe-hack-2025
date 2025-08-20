# In backend/core/podcast.py

import os
import subprocess
import requests
from pathlib import Path
import re
import concurrent.futures # Import for parallel processing


# --- Dependencies for this module ---
# Make sure to add these to your requirements.txt:
# requests
# google-cloud-texttospeech
# pydub

from typing import List
from app.schemas.podcast import PodcastSegment # Import the new PodcastSegment schema

def create_podcast_from_script(script_segments: List[PodcastSegment], output_file: str, provider: str = None):
    from pydub import AudioSegment

    if not script_segments:
        raise ValueError("Podcast script segments cannot be empty.")

    voice_map = {
        "host": {"azure": "alloy", "gcp": "en-US-Wavenet-C", "local": "en-us+f3"}, # Female voice
        "guest": {"azure": "onyx", "gcp": "en-US-Wavenet-D", "local": "en-us"},   # Male voice
        "alex": {"azure": "alloy", "gcp": "en-US-Wavenet-C", "local": "en-us+f3"}, # Keep for backward compatibility if "alex" is used elsewhere
        "ben": {"azure": "onyx", "gcp": "en-US-Wavenet-D", "local": "en-us"},   # Keep for backward compatibility if "ben" is used elsewhere
    }

    temp_files = []
    output_path = Path(output_file)

    try:
        # Sort segments by their order to ensure correct processing sequence
        script_segments.sort(key=lambda s: s.order)
        
        # Use ThreadPoolExecutor for parallel audio generation
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Create a list of futures, maintaining the original order for result collection
            futures = []
            for i, segment in enumerate(script_segments):
                speaker_lower = segment.speaker.strip().lower()
                # Get the dictionary of voices for the speaker, defaulting to 'alex' if not found
                speaker_voices = voice_map.get(speaker_lower, voice_map.get("alex"))
                
                # Select the specific voice for the current provider
                # Default to a generic voice if the provider-specific voice is not found
                if isinstance(speaker_voices, dict):
                    selected_voice = speaker_voices.get(provider, speaker_voices.get("azure")) # Fallback to azure voice if provider not explicitly mapped
                else:
                    selected_voice = speaker_voices # Fallback for old string-based voice_map entries

                temp_file_name = f".podcast_chunk_{i}.mp3" # Use enumerate index for temp file name
                temp_file_path = str(output_path.parent / temp_file_name)
                
                futures.append(executor.submit(generate_audio, segment.dialogue, temp_file_path, provider, selected_voice))

            # Collect results in order of submission
            generated_audio_paths = []
            for i, future in enumerate(futures):
                try:
                    audio_file_path = future.result()
                    generated_audio_paths.append(audio_file_path)
                    temp_files.append(audio_file_path)
                except Exception as exc:
                    print(f"Segment {i} generated an exception: {exc}")
                    raise

        combined_audio = AudioSegment.empty()
        for audio_file_path in generated_audio_paths:
            if audio_file_path: # Ensure no None values if an exception occurred
                segment_audio = AudioSegment.from_mp3(audio_file_path)
                combined_audio += segment_audio

        combined_audio.export(str(output_path), format="mp3")
        return str(output_path)
    finally:
        for tf in temp_files:
            try: os.remove(tf)
            except OSError: pass



def generate_audio(text, output_file, provider=None, voice=None):
    """
    Generate audio from text using the specified TTS provider.
    """
    if not text or not text.strip():
        raise ValueError("Text cannot be empty")

    provider = provider or os.getenv("TTS_PROVIDER", "local").lower()

    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    max_chars_env = os.getenv("TTS_CLOUD_MAX_CHARS", "3000")
    max_chars = None
    try:
        max_chars = int(max_chars_env)
        if max_chars <= 0:
            max_chars = None
    except (TypeError, ValueError):
        max_chars = 3000

    if provider in ("azure", "gcp") and max_chars and len(text) > max_chars:
        return _generate_cloud_tts_chunked(text, output_file, provider, voice, max_chars)

    if provider == "azure":
        return _generate_azure_tts(text, output_file, voice)
    elif provider == "gcp":
        return _generate_gcp_tts(text, output_file, voice)
    elif provider == "local":
        return _generate_local_tts(text, output_file, voice)
    else:
        raise ValueError(f"Unsupported TTS_PROVIDER: {provider}")


def _chunk_text_by_chars(text, max_chars):
    """Split text into chunks not exceeding max_chars, preferring whitespace boundaries."""
    import re
    if len(text) <= max_chars:
        return [text]
    tokens = re.findall(r"\S+\s*", text)
    chunks = []
    current = ""
    for token in tokens:
        if len(current) + len(token) <= max_chars:
            current += token
        else:
            if current:
                chunks.append(current.strip())
            current = token
            while len(current) > max_chars:
                chunks.append(current[:max_chars])
                current = current[max_chars:]
    if current.strip():
        chunks.append(current.strip())
    return [c for c in chunks if c]


def _generate_cloud_tts_chunked(text, output_file, provider, voice, max_chars):
    """Chunk long text for cloud providers and concatenate resulting audio files."""
    from pydub import AudioSegment

    chunks = _chunk_text_by_chars(text, max_chars)
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    temp_files = []
    try:
        for index, chunk in enumerate(chunks):
            temp_file = str(output_path.parent / f".tts_chunk_{index}.mp3")
            if provider == "azure":
                _generate_azure_tts(chunk, temp_file, voice)
            elif provider == "gcp":
                _generate_gcp_tts(chunk, temp_file, voice)
            else:
                raise ValueError("Chunked synthesis is only for 'azure' and 'gcp'.")
            temp_files.append(temp_file)

        combined_audio = AudioSegment.empty()
        for temp_file in temp_files:
            segment = AudioSegment.from_mp3(temp_file)
            combined_audio += segment

        suffix = output_path.suffix.lower().lstrip(".") or "mp3"
        combined_audio.export(str(output_path), format=suffix)

        print(f"Chunked {provider.upper()} TTS audio saved to: {output_file} ({len(chunks)} chunks)")
        return str(output_path)
    finally:
        for temp_file in temp_files:
            try:
                os.remove(temp_file)
            except OSError:
                pass


def _generate_azure_tts(text, output_file, voice=None):
    """Generate audio using Azure OpenAI TTS."""
    api_key = os.getenv("AZURE_TTS_KEY")
    endpoint = os.getenv("AZURE_TTS_ENDPOINT")
    deployment_name = os.getenv("AZURE_TTS_DEPLOYMENT", "tts")
    api_version = os.getenv("AZURE_TTS_API_VERSION", "2025-03-01-preview")
    voice = voice or os.getenv("AZURE_TTS_VOICE", "alloy") # Default voice for Azure OpenAI TTS. This will be overridden by voice_map if a specific speaker is provided.

    if not all([api_key, endpoint, deployment_name, api_version]):
        raise ValueError("AZURE_TTS_KEY, AZURE_TTS_ENDPOINT, AZURE_TTS_DEPLOYMENT, and AZURE_TTS_API_VERSION must be set for Azure OpenAI TTS")

    # Azure OpenAI Service TTS endpoint format
    tts_url = f"{endpoint}/openai/deployments/{deployment_name}/audio/speech?api-version={api_version}"
    
    tts_headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
    }

    json_body = {
        "model": deployment_name,
        "input": text,
        "voice": voice,
        "response_format": "mp3"
    }

    try:
        tts_response = requests.post(tts_url, headers=tts_headers, json=json_body, timeout=30)
        tts_response.raise_for_status()

        with open(output_file, "wb") as f:
            f.write(tts_response.content)

        return output_file
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Azure TTS failed: {e}")


def _generate_gcp_tts(text, output_file, voice=None):
    """Generate audio using Google Cloud TTS."""
    from google.cloud import texttospeech
    from pydub import AudioSegment

    # Ensure GOOGLE_APPLICATION_CREDENTIALS environment variable is set
    # or provide credentials directly. For simplicity, we assume it's set.
    # client = texttospeech.TextToSpeechClient.from_service_account_json("path/to/your/key.json")
    client = texttospeech.TextToSpeechClient()

    voice_name = voice or os.getenv("GCP_TTS_VOICE", "en-US-Wavenet-D") # This will be overridden by voice_map if a specific speaker is provided.
    
    synthesis_input = texttospeech.SynthesisInput(text=text)

    # Select the type of audio file you want to use.
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )

    # Select the language and SSML voice gender your app will use.
    voice_selection_params = texttospeech.VoiceSelectionParams(
        language_code="en-US",
        name=voice_name,
    )

    try:
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice_selection_params,
            audio_config=audio_config
        )

        # The response's audio_content is binary.
        with open(output_file, "wb") as out:
            out.write(response.audio_content)
        
        return output_file
    except Exception as e:
        raise RuntimeError(f"Google Cloud TTS failed: {e}")


def _generate_local_tts(text, output_file, voice=None):
    """Generate audio using local espeak-ng."""
    espeak_voice = voice or os.getenv("ESPEAK_VOICE", "en") # This will be overridden by voice_map if a specific speaker is provided.
    espeak_speed = os.getenv("ESPEAK_SPEED", "150")

    temp_wav_file = str(Path(output_file).with_suffix('.wav'))

    try:
        cmd = ['espeak-ng', '-v', espeak_voice, '-s', str(espeak_speed), '-w', temp_wav_file, text]
        subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=True)

        if Path(output_file).suffix.lower() == '.mp3':
            from pydub import AudioSegment
            audio = AudioSegment.from_wav(temp_wav_file)
            audio.export(output_file, format="mp3")
            os.remove(temp_wav_file)

        return output_file
    except FileNotFoundError:
        raise RuntimeError("espeak-ng not found. Please install it.")
    except Exception as e:
        raise RuntimeError(f"Local TTS synthesis error: {e}")
