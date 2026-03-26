import whisper

model = whisper.load_model("base")

result = model.transcribe("user_audio.wav")
text = result["text"]

print(text)