import inspect
from cartesia import Cartesia
from cartesia.tts import TTS

print(inspect.signature(TTS.bytes))
print(dir(TTS))
