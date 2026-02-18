import cartesia
import inspect

print("Cartesia dir:", dir(cartesia))
if hasattr(cartesia, 'Cartesia'):
    client = cartesia.Cartesia(api_key="dummy")
    print("Client dir:", dir(client))
    if hasattr(client, 'tts'):
        print("Client.tts dir:", dir(client.tts))
        if hasattr(client.tts, 'bytes'):
            print("Client.tts.bytes signature:", inspect.signature(client.tts.bytes))
        elif hasattr(client.tts, 'generate'): # Maybe it's generate?
             print("Client.tts.generate signature:", inspect.signature(client.tts.generate))
