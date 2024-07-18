#! python -u

import os
import pyaudio
from six.moves import queue
from google.cloud import speech_v1p1beta1 as speech
import threading
from google.cloud import texttospeech
from pydub import AudioSegment
from io import BytesIO
from pydub.playback import play
from google.api_core.exceptions import GoogleAPICallError, InvalidArgument
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog 
import socketio

# Initialize SocketIO client
sio = socketio.Client()

# Connect to the server
sio.connect('http://localhost:5000')

# theme and color
ctk.set_appearance_mode("Light")

# Set the environment variable for authentication
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "your_path-google_cloud_api_key.json"

RATE = 16000
CHUNK = int(RATE/10)

class MicrophoneStream(object):
    def __init__(self, rate, chunk):
        self.rate = rate
        self.chunk = chunk
        self.buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        self.audio_interface = pyaudio.PyAudio()
        self.audio_stream = self.audio_interface.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=self.rate,
            input=True,
            frames_per_buffer=self.chunk,
            stream_callback=self._fill_buffer,
        )
        self.closed = False
        return self

    def __exit__(self, type, value, traceback):
        if self.audio_stream:
            self.audio_stream.stop_stream()
            self.audio_stream.close()
            self.closed = True
            self.buff.put(None)
            self.audio_interface.terminate()
        

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        self.buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            chunk = self.buff.get()
            if chunk is None:
                return
            data = [chunk]
            while True:
                try:
                    chunk = self.buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break
            yield b"".join(data)
def listen_print_loop(responses , textbox):
    try:
        for response in responses:
            if not response.results:
                continue
            result = response.results[0]
            if not result.alternatives:
                continue
            
            transcript = result.alternatives[0].transcript    
            if result.is_final:
                textbox.configure(state=tk.NORMAL)
                textbox.insert(tk.END , transcript)
                textbox.configure(state=tk.DISABLED)
                textbox.see(tk.END)
            
    except (GoogleAPICallError, InvalidArgument) as e:
        print(e)
        
class MyFrame_1(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.client = speech.SpeechClient()
        self.stream = None  # Initialize stream attribute

        # frame_1 title
        self.label_1 = ctk.CTkLabel(self, text="SPEECH TO TEXT", font=("Arial", 16), corner_radius=4, width=500, height=35)
        self.label_1.grid(row=0, column=0, padx=10, pady=10)
        
        # frame_1 textbox
        self.label_2 = ctk.CTkTextbox(self, fg_color="#fff", font=("Arial", 16), corner_radius=4, width=500, height=200, padx=10, pady=10)
        self.label_2.grid(row=1, column=0, padx=10)
        
        # frame_1 button
        self.label_3 = ctk.CTkButton(self, text="Start Record", fg_color="#008000", font=("Arial", 16), corner_radius=4, width=150, height=35, hover_color="#008000", command=self.toggle_recording)
        self.label_3.grid(row=2, column=0, padx=10, pady=10, sticky="ne")
        
        # frame_1 language menu
        self.language_var = tk.StringVar(value="en-US")
        self.language_menu = ctk.CTkOptionMenu(self, variable=self.language_var, values=["en-US", "en-IN"], corner_radius=4, width=150, height=35, font=("Arial", 16))
        self.language_menu.grid(row=2, column=0, padx=10, pady=10, sticky="nw")
        
        # frame_1 saves button
        self.label_4 = ctk.CTkButton(self, text="Save File", font=("Arial", 16), corner_radius=4, width=150, height=35, hover_color="#008000" , command=self.save_file_function)
        self.label_4.grid(row=2, column=0, padx=10, pady=10)
        
        # variables
        self.recording = False
        self.text = ""
        
        # SocketIO event handler
        sio.on('transcription')(self.handle_transcription)
    
    def handle_transcription(self,data):
        self.label_2.insert(tk.END, "\n")
        self.label_2.configure(state="normal")
        self.label_2.insert(tk.END, data)
        self.label_2.configure(state="disabled")
        self.label_2.see(tk.END)
    
    def save_file_function(self):
        text_to_file = self.label_2.get("1.0", tk.END).strip()
        remove_strings = ["Recording audio...", "Recording stopped."]
        for remove_str in remove_strings:
            text_to_file = text_to_file.replace(remove_str, "")        
        if text_to_file:
            file_path = filedialog.asksaveasfilename(defaultextension=".txt", filetypes=[("Text files", "*.txt"), ("All files", "*.*")])
            if file_path:
                with open(file_path, "w") as file:
                    file.write(text_to_file)
                print(f"Saved text to {file_path}")

    # toggle recording button
    def toggle_recording(self):
        if not self.recording:
            self.start_recording_btn()
        else:
            self.stop_recording_btn()

    # start recording function
    def start_recording_btn(self):
        self.recording = True
        self.label_3.configure(text="Stop Record" , fg_color="#FF0000",hover_color="#FF0000")
        self.label_2.configure(state="normal")
        self.label_2.insert(tk.END, "Recording audio...\n")
        self.label_2.configure(state="disabled")
        
        if not self.stream:
            self.stream = MicrophoneStream(RATE, CHUNK)
            threading.Thread(target=self.transcribe).start()
            print("Recording audio...")
        else:
            print("Stream is already open.")

    # stop recording function
    def stop_recording_btn(self):
        self.recording = False
        self.label_3.configure(text="Start Record" , fg_color="#008000" , hover_color="#008000")
        self.label_2.configure(state="normal")
        self.label_2.insert(tk.END, "\nRecording stopped.\n")
        self.label_2.configure(state="disabled")
        if self.stream:
            self.stream.__exit__(None, None, None)
            self.stream = None
            print("Recording stopped.\n")
        else:
            print("No active stream to close.\n")

    
    # transcribe function
    def transcribe(self):
        if self.stream:
            with self.stream:
                config = speech.RecognitionConfig(
                    encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
                    sample_rate_hertz=RATE,
                    language_code=self.language_var.get(),
                    model="default",
                    enable_automatic_punctuation=True,
                    enable_word_confidence=True,
                )
                streaming_config = speech.StreamingRecognitionConfig(
                    config=config,
                    interim_results=True,
                )
                audio_generator = self.stream.generator()
                try:
                    while True:
                        requests = (speech.StreamingRecognizeRequest(audio_content=content) for content in audio_generator)
                        responses = self.client.streaming_recognize(streaming_config, requests)
                        listen_print_loop(responses, self.label_2)
                except Exception as e:
                    print(f"Error: {e}")
                finally:
                    self.stream.stop_stream()
                    self.stream.close()
                    self.audio.terminate()
    
    
        
class MyFrame_2(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)

        self.client = texttospeech.TextToSpeechClient()
        # frame_2 title
        self.label_1 = ctk.CTkLabel(self, text="TEXT TO SPEECH", font=("Arial", 16), corner_radius=4, width=500, height=35)
        self.label_1.grid(row=0, column=0, padx=10, pady=10)
        
        # frame_3 textbox
        self.label_2 = ctk.CTkTextbox(self, fg_color="#fff", font=("Arial", 16), corner_radius=4, width=500, height=200, padx=10, pady=10)
        self.label_2.grid(row=1, column=0, padx=10)
        
        # frame_1 button
        self.label_3 = ctk.CTkButton(self, text="CLEAR", font=("Arial", 16), corner_radius=4, width=150, height=35, command=self.clear_text_box)
        self.label_3.grid(row=2, column=0, padx=10, pady=10, sticky="ne")
        
        # bind <RETURN> key press to speak function
        self.label_2.bind("<Return>" , self.speech_fun)
    
    # speech function
    def speech_fun(self , event):
        _text = self.label_2.get("end-1l", "end-1c")  # Get all text from line 1, character 0 to the end
        
        if _text.strip():
            threading.Thread(target=self.text_to_speech, args=(_text,)).start()
            
    # text to speech configuration
    def text_to_speech(self, text):
        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice = texttospeech.VoiceSelectionParams(
            language_code='en-US',  # Language code (e.g., 'en-US')
            ssml_gender=texttospeech.SsmlVoiceGender.NEUTRAL  # Gender of the voice (optional)
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,  # Output audio format (e.g., MP3)
            speaking_rate=0.75
            
        )
        response = self.client.synthesize_speech(input=synthesis_input, voice=voice, audio_config=audio_config)

        # Play the audio directly without saving to file
        audio_data = response.audio_content
        play(AudioSegment.from_file(BytesIO(audio_data)))
        
    # clear function
    def clear_text_box(self):
        self.label_2.delete("1.0" , tk.END)

class App(ctk.CTk):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.title('Speech Recognition')
        
        self.grid_rowconfigure(0, weight=1)  # configure grid system
        self.grid_columnconfigure(0, weight=1)

        self.my_frame_1 = MyFrame_1(master=self , fg_color="#cccccc")
        self.my_frame_1.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        self.my_frame_2 = MyFrame_2(master=self , fg_color="#cccccc")
        self.my_frame_2.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        
        # Bind closing event to the destroy method of the App instance
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def on_close(self):
        # Handle closing event gracefully
        print("close")
        self.destroy()

if __name__ == "__main__":
    app = App()
    app.mainloop()