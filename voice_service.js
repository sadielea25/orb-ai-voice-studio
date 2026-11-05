import { ElevenLabsClient } from "@elevenlabs/elevenlabs-js";

// The SDK automatically reads ELEVENLABS_API_KEY from environment variables
const elevenlabs = new ElevenLabsClient();

export async function generateSpeech({ text, voiceId = "Xb7hH8MSUJpSbSDYk0k2", modelId = "eleven_turbo_v2_5" }) {
  const audioStream = await elevenlabs.textToSpeech.convert(voiceId, {
    text,
    model_id: modelId,
  });
  return audioStream;
}

export default elevenlabs;
