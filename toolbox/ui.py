import sys
from pathlib import Path
from time import sleep
from typing import List, Set
from warnings import filterwarnings, warn

import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
import pandas as pd
import sounddevice as sd
import soundfile as sf
import umap
from PyQt5.QtCore import Qt, QStringListModel
from PyQt5.QtWidgets import *
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

from speaker_encoder.inference import plot_embedding_as_heatmap
from toolbox.utterance import Utterance

filterwarnings("ignore")


colormap = np.array([
    [0, 127, 70],
    [255, 0, 0],
    [255, 217, 38],
    [0, 135, 255],
    [165, 0, 165],
    [255, 167, 255],
    [97, 142, 151],
    [0, 255, 255],
    [255, 96, 38],
    [142, 76, 0],
    [33, 0, 127],
    [0, 0, 0],
    [183, 183, 183],
    [76, 255, 0],
], dtype=np.float) / 255

default_text = \
    "I visited museums and sat in public gardens"


class UI(QDialog):
    min_umap_points = 4
    max_log_lines = 5
    max_log_width = 100
    max_saved_utterances = 20

    def draw_utterance(self, utterance: Utterance, which):
        self.draw_spec(utterance.spec, which)
        self.draw_embed(utterance.speaker_embed, utterance.emotion_embed, utterance.name, which)

    def draw_embed(self, speaker_embed, emotion_embed, name, which):
        speaker_embed_ax, emotion_embed_ax, _ = self.current_ax if which == "current" else self.gen_ax
        speaker_embed_ax.figure.suptitle("" if speaker_embed is None else name)
        emotion_embed_ax.figure.suptitle("" if emotion_embed is None else name)

        ## Speaker Embedding
        # Clear the plot
        if len(speaker_embed_ax.images) > 0:
            speaker_embed_ax.images[0].colorbar.remove()
        speaker_embed_ax.clear()

        # Draw the embed
        if speaker_embed is not None:
            plot_embedding_as_heatmap(speaker_embed, speaker_embed_ax)
            speaker_embed_ax.set_title("speaker embed")
        speaker_embed_ax.set_aspect("equal", "datalim")
        speaker_embed_ax.set_xticks([])
        speaker_embed_ax.set_yticks([])
        speaker_embed_ax.figure.canvas.draw()

        ## Emotion Embedding
        # Clear the plot
        if len(emotion_embed_ax.images) > 0:
            emotion_embed_ax.images[0].colorbar.remove()
        emotion_embed_ax.clear()

        # Draw the embed
        if emotion_embed is not None:
            plot_embedding_as_heatmap(emotion_embed, emotion_embed_ax, shape=(13, 3))
            emotion_embed_ax.set_title("emotion embed")
        emotion_embed_ax.set_aspect("equal", "datalim")
        emotion_embed_ax.set_xticks([])
        emotion_embed_ax.set_yticks([])
        emotion_embed_ax.figure.canvas.draw()

    def draw_spec(self, spec, which):
        _, _, spec_ax = self.current_ax if which == "current" else self.gen_ax

        ## Spectrogram
        # Draw the spectrogram
        spec_ax.clear()
        if spec is not None:
            spec_ax.imshow(spec, aspect="auto", interpolation="none")
            spec_ax.set_title("mel spectrogram")

        spec_ax.set_xticks([])
        spec_ax.set_yticks([])
        spec_ax.figure.canvas.draw()
        if which != "current":
            self.vocode_button.setDisabled(spec is None)

    def draw_umap_projections(self, utterances: Set[Utterance]):
        def umap_progress(i, seq_len):
            self.set_loading(i, seq_len)
        speaker_umap_ax, emotion_umap_ax = self.umap_ax

        # draw speaker embeddings umap 
        speaker_umap_ax.clear()

        utterances = list(utterances)
        speakers = np.unique([u.speaker_name for u in utterances])
        colors = {speaker_name: colormap[i] for i, speaker_name in enumerate(speakers)}
        embeds = [u.speaker_embed for u in utterances]

        # Display a message if there aren't enough points
        if len(utterances) < self.min_umap_points:
            speaker_umap_ax.text(.5, .5, "Add %d more points to\ngenerate the projections" %
                              (self.min_umap_points - len(utterances)),
                              horizontalalignment='center', fontsize=15)

        # Compute the projections
        else:
            if not self.umap_hot:
                self.log(
                    "Drawing UMAP projections for the first time, this will take a few seconds.")
                self.umap_hot = True

            reducer = umap.UMAP(int(np.ceil(np.sqrt(len(embeds)))), metric="cosine")
            projections = reducer.fit_transform(embeds)

            colors = [colors[u.speaker_name] for u in utterances]
            markers = ["x" if "_gen_" in u.name else "o" for u in utterances]
            # labels = [u.speaker_name for u in utterances]
            # speakers_done.add(utterance.speaker_name)
            i = 0
            for x, y, c, m in zip(projections[:, 0], projections[:,1], colors, markers):
                i+=1
                speaker_umap_ax.scatter(x=x, y=y, c=c, marker=m)
                self.set_loading(i, projections.shape[0])
            speaker_umap_ax.set_title("Speaker Embedding UMAP")
            self.set_loading(0)

        # Draw the plot
        speaker_umap_ax.set_aspect("equal", "datalim")
        speaker_umap_ax.set_xticks([])
        speaker_umap_ax.set_yticks([])
        speaker_umap_ax.figure.canvas.draw()

        # draw emotion embeddings umap 
        emotion_umap_ax.clear()

        utterances = list(utterances)
        speakers = np.unique([u.speaker_name for u in utterances])
        colors = {speaker_name: colormap[i] for i, speaker_name in enumerate(speakers)}
        embeds = [u.emotion_embed for u in utterances]

        # Display a message if there aren't enough points
        if len(utterances) < self.min_umap_points:
            emotion_umap_ax.text(.5, .5, "Add %d more points to\ngenerate the projections" %
                              (self.min_umap_points - len(utterances)),
                              horizontalalignment='center', fontsize=15)
            
        # Compute the projections
        else:
            if not self.umap_hot:
                self.log(
                    "Drawing UMAP projections for the first time, this will take a few seconds.")
                self.umap_hot = True

            reducer = umap.UMAP(int(np.ceil(np.sqrt(len(embeds)))), metric="cosine")
            projections = reducer.fit_transform(embeds)

            colors = [colors[u.speaker_name] for u in utterances]
            markers = ["x" if "_gen_" in u.name else "o" for u in utterances]
            # labels = [u.speaker_name for u in utterances]
            # speakers_done.add(utterance.speaker_name)
            i = 0
            for x, y, c, m in zip(projections[:, 0], projections[:,1], colors, markers):
                i+=1
                emotion_umap_ax.scatter(x=x, y=y, c=c, marker=m)
                self.set_loading(i, projections.shape[0])
            emotion_umap_ax.set_title("Emotion Embedding UMAP")
            self.set_loading(0)

        # Draw the plot
        emotion_umap_ax.set_aspect("equal", "datalim")
        emotion_umap_ax.set_xticks([])
        emotion_umap_ax.set_yticks([])
        emotion_umap_ax.figure.canvas.draw()

    def save_audio_file(self, wav, sample_rate):
        dialog = QFileDialog()
        dialog.setDefaultSuffix(".wav")
        fpath, _ = dialog.getSaveFileName(
            parent=self,
            caption="Select a path to save the audio file",
            filter="Audio Files (*.flac *.wav)"
        )
        if fpath:
            #Default format is wav
            if Path(fpath).suffix == "":
                fpath += ".wav"
            sf.write(fpath, wav, sample_rate)

    def setup_audio_devices(self, sample_rate):
        input_devices = []
        output_devices = []
        for device in sd.query_devices():
            # Check if valid input
            try:
                sd.check_input_settings(device=device["name"], samplerate=sample_rate)
                input_devices.append(device["name"])
            except:
                pass

            # Check if valid output
            try:
                sd.check_output_settings(device=device["name"], samplerate=sample_rate)
                output_devices.append(device["name"])
            except Exception as e:
                # Log a warning only if the device is not an input
                if not device["name"] in input_devices:
                    warn("Unsupported output device %s for the sample rate: %d \nError: %s" % (device["name"], sample_rate, str(e)))

        if len(input_devices) == 0:
            self.log("No audio input device detected. Recording may not work.")
            self.audio_in_device = None
        else:
            self.audio_in_device = input_devices[0]

        if len(output_devices) == 0:
            self.log("No supported output audio devices were found! Audio output may not work.")
            self.audio_out_devices_cb.addItems(["None"])
            self.audio_out_devices_cb.setDisabled(True)
        else:
            self.audio_out_devices_cb.clear()
            self.audio_out_devices_cb.addItems(output_devices)
            self.audio_out_devices_cb.currentTextChanged.connect(self.set_audio_device)

        self.set_audio_device()

    def set_audio_device(self):

        output_device = self.audio_out_devices_cb.currentText()
        if output_device == "None":
            output_device = None

        # If None, sounddevice queries portaudio
        sd.default.device = (self.audio_in_device, output_device)

    def play(self, wav, sample_rate):
        try:
            sd.stop()
            sd.play(wav, sample_rate)
        except Exception as e:
            print(e)
            self.log("Error in audio playback. Try selecting a different audio output device.")
            self.log("Your device must be connected before you start the toolbox.")

    def stop(self):
        sd.stop()

    def record_one(self, sample_rate, duration):
        self.record_button.setText("Recording...")
        self.record_button.setDisabled(True)

        self.log("Recording %d seconds of audio" % duration)
        sd.stop()
        try:
            wav = sd.rec(duration * sample_rate, sample_rate, 1)
        except Exception as e:
            print(e)
            self.log("Could not record anything. Is your recording device enabled?")
            self.log("Your device must be connected before you start the toolbox.")
            return None

        for i in np.arange(0, duration, 0.1):
            self.set_loading(i, duration)
            sleep(0.1)
        self.set_loading(duration, duration)
        sd.wait()

        self.log("Done recording.")
        self.record_button.setText("Record")
        self.record_button.setDisabled(False)

        return wav.squeeze()

    @property
    def current_dataset_name(self):
        return self.dataset_box.currentText()

    @property
    def current_speaker_name(self):
        return self.speaker_box.currentText()

    @property
    def current_utterance_name(self):
        return self.utterance_box.currentText()

    def browse_file(self):
        fpath = QFileDialog().getOpenFileName(
            parent=self,
            caption="Select an audio file",
            filter="Audio Files (*.mp3 *.flac *.wav *.m4a)"
        )
        return Path(fpath[0]) if fpath[0] != "" else ""

    @staticmethod
    def repopulate_box(box, items, random=False):
        """
        Resets a box and adds a list of items. Pass a list of (item, data) pairs instead to join
        data to the items
        """
        box.blockSignals(True)
        box.clear()
        for item in items:
            item = list(item) if isinstance(item, tuple) else [item]
            box.addItem(str(item[0]), *item[1:])
        if len(items) > 0:
            box.setCurrentIndex(np.random.randint(len(items)) if random else 0)
        box.setDisabled(len(items) == 0)
        box.blockSignals(False)

    def populate_browser(self, datasets_root: Path, recognized_datasets: List, level: int,
                         random=True):
        # Select a random dataset
        if level <= 0:
            if datasets_root is not None:
                datasets = [datasets_root.joinpath(d) for d in recognized_datasets]
                datasets = [d.relative_to(datasets_root) for d in datasets if d.exists()]
                self.browser_load_button.setDisabled(len(datasets) == 0)
            if datasets_root is None or len(datasets) == 0:
                msg = "Warning: you d" + ("id not pass a root directory for datasets as argument" \
                    if datasets_root is None else "o not have any of the recognized datasets" \
                                                  " in %s" % datasets_root)
                self.log(msg)
                msg += ".\nThe recognized datasets are:\n\t%s\nFeel free to add your own. You " \
                       "can still use the toolbox by recording samples yourself." % \
                       ("\n\t".join(recognized_datasets))
                print(msg, file=sys.stderr)

                self.random_utterance_button.setDisabled(True)
                self.random_speaker_button.setDisabled(True)
                self.random_dataset_button.setDisabled(True)
                self.utterance_box.setDisabled(True)
                self.speaker_box.setDisabled(True)
                self.dataset_box.setDisabled(True)
                self.browser_load_button.setDisabled(True)
                self.auto_next_checkbox.setDisabled(True)
                return
            self.repopulate_box(self.dataset_box, datasets, random)

        # Select a random speaker
        if level <= 1:
            speakers_root = datasets_root.joinpath(self.current_dataset_name)
            speaker_names = [d.stem for d in speakers_root.glob("*") if d.is_dir()]
            self.repopulate_box(self.speaker_box, speaker_names, random)

        # Select a random utterance
        if level <= 2:
            utterances_root = datasets_root.joinpath(
                self.current_dataset_name,
                self.current_speaker_name
            )
            utterances = []
            for extension in ['mp3', 'flac', 'wav', 'm4a']:
                utterances.extend(Path(utterances_root).glob("**/*.%s" % extension))
            utterances = [fpath.relative_to(utterances_root) for fpath in utterances]
            self.repopulate_box(self.utterance_box, utterances, random)

    def browser_select_next(self):
        index = (self.utterance_box.currentIndex() + 1) % len(self.utterance_box)
        self.utterance_box.setCurrentIndex(index)

    @property
    def current_speaker_encoder_fpath(self):
        return self.speaker_encoder_box.itemData(self.speaker_encoder_box.currentIndex())
    
    @property
    def current_emotion_encoder_fpath(self):
        return self.emotion_encoder_box.itemData(self.emotion_encoder_box.currentIndex())

    @property
    def current_synthesizer_fpath(self):
        return self.synthesizer_box.itemData(self.synthesizer_box.currentIndex())

    @property
    def current_vocoder_fpath(self):
        return self.vocoder_box.itemData(self.vocoder_box.currentIndex())

    def populate_models(self, run_id: str, models_dir: Path):
        # Speaker Encoder
        speaker_encoder_fpaths = list(models_dir.glob(f"{run_id}/encoder.pt"))
        if len(speaker_encoder_fpaths) == 0:
            raise Exception("No speaker encoder models found in %s" % models_dir)
        self.repopulate_box(self.speaker_encoder_box, [(f.parent.name, f) for f in speaker_encoder_fpaths])

        # Emotion Encoder
        emotion_encoder_fpaths = list(models_dir.glob(f"{run_id}/**/*.hdf5"))
        if len(emotion_encoder_fpaths) == 0:
            raise Exception("No emotion encoder models found in %s" % models_dir)
        self.repopulate_box(self.emotion_encoder_box, [(f.parent.parent.name, f) for f in emotion_encoder_fpaths])

        # Synthesizer
        synthesizer_fpaths = list(models_dir.glob(f"{run_id}/synthesizer.pt"))
        if len(synthesizer_fpaths) == 0:
            raise Exception("No synthesizer models found in %s" % models_dir)
        self.repopulate_box(self.synthesizer_box, [(f.parent.name, f) for f in synthesizer_fpaths])

        # Vocoder
        vocoder_fpaths = list(models_dir.glob(f"{run_id}/vocoder.pt"))
        vocoder_items = [(f.parent.name, f) for f in vocoder_fpaths] + [("Griffin-Lim", None)]
        self.repopulate_box(self.vocoder_box, vocoder_items)

    @property
    def selected_utterance(self):
        return self.utterance_history.itemData(self.utterance_history.currentIndex())

    def register_utterance(self, utterance: Utterance):
        self.utterance_history.blockSignals(True)
        self.utterance_history.insertItem(0, utterance.name, utterance)
        self.utterance_history.setCurrentIndex(0)
        self.utterance_history.blockSignals(False)

        if len(self.utterance_history) > self.max_saved_utterances:
            self.utterance_history.removeItem(self.max_saved_utterances)

        self.play_button.setDisabled(False)
        self.generate_button.setDisabled(False)
        self.synthesize_button.setDisabled(False)

    def log(self, line, mode="newline"):
        if mode == "newline":
            if len(line) > self.max_log_width:
                num_lines = len(line) // self.max_log_width
                res = len(line) - (len(line) // self.max_log_width) * self.max_log_width
                for l in range(num_lines):
                    self.logs.append(line[l *self.max_log_width : (l+1)*self.max_log_width])
                    if len(self.logs) > self.max_log_lines:
                        del self.logs[0]
                self.logs.append(line[-res-1: ])
            else:             
                self.logs.append(line)
            if len(self.logs) > self.max_log_lines:
                del self.logs[0]
        elif mode == "append":
            self.logs[-1] += line
        elif mode == "overwrite":
            self.logs[-1] = line
        log_text = '\n'.join(self.logs)

        self.log_window.setText(log_text)
        self.app.processEvents()

    def set_loading(self, value, maximum=1):
        self.loading_bar.setValue(value * 100)
        self.loading_bar.setMaximum(maximum * 100)
        self.loading_bar.setTextVisible(value != 0)
        self.app.processEvents()

    def populate_gen_options(self, seed, trim_silences):
        if seed is not None:
            self.random_seed_checkbox.setChecked(True)
            self.seed_textbox.setText(str(seed))
            self.seed_textbox.setEnabled(True)
        else:
            self.random_seed_checkbox.setChecked(False)
            self.seed_textbox.setText(str(0))
            self.seed_textbox.setEnabled(False)

        if not trim_silences:
            self.trim_silences_checkbox.setChecked(False)
            self.trim_silences_checkbox.setDisabled(True)

    def update_seed_textbox(self):
        if self.random_seed_checkbox.isChecked():
            self.seed_textbox.setEnabled(True)
        else:
            self.seed_textbox.setEnabled(False)

    def reset_interface(self):
        self.draw_embed(None, None, None, "current")
        self.draw_embed(None, None, None, "generated")
        self.draw_spec(None, "current")
        self.draw_spec(None, "generated")
        self.draw_umap_projections(set())
        self.set_loading(0)
        self.play_button.setDisabled(True)
        self.generate_button.setDisabled(True)
        self.synthesize_button.setDisabled(True)
        self.vocode_button.setDisabled(True)
        self.replay_wav_button.setDisabled(True)
        self.export_wav_button.setDisabled(True)
        [self.log("") for _ in range(self.max_log_lines)]

    def __init__(self):
        ## Initialize the application
        self.app = QApplication(sys.argv)
        super().__init__(None)
        self.setWindowTitle("SV2TTS toolbox")


        ## Main layouts
        # Root
        root_layout = QGridLayout()
        self.setLayout(root_layout)

        # Browser
        browser_layout = QGridLayout()
        root_layout.addLayout(browser_layout, 0, 0, 1, 2)

        # Generation
        gen_layout = QVBoxLayout()
        root_layout.addLayout(gen_layout, 0, 2, 1, 1)

        # Projections
        self.projections_layout = QVBoxLayout()
        root_layout.addLayout(self.projections_layout, 1, 0, 1, 1)

        # Visualizations
        vis_layout = QVBoxLayout()
        root_layout.addLayout(vis_layout, 1, 1, 1, 3)


        ## Projections
        # UMap
        self.umap_fig, self.umap_ax = plt.subplots(2, 1, figsize=(3, 3), facecolor="#F0F0F0")
        self.umap_fig.subplots_adjust(left=0.02, bottom=0.02, right=0.98, top=0.9)
        self.projections_layout.addWidget(FigureCanvas(self.umap_fig))
        self.umap_hot = False
        self.clear_button = QPushButton("Clear")
        self.projections_layout.addWidget(self.clear_button)


        ## Browser
        # Dataset, speaker and utterance selection
        i = 0
        self.dataset_box = QComboBox()
        browser_layout.addWidget(QLabel("<b>Dataset</b>"), i, 0)
        browser_layout.addWidget(self.dataset_box, i + 1, 0)
        self.speaker_box = QComboBox()
        browser_layout.addWidget(QLabel("<b>Speaker</b>"), i, 1)
        browser_layout.addWidget(self.speaker_box, i + 1, 1)
        self.utterance_box = QComboBox()
        browser_layout.addWidget(QLabel("<b>Utterance</b>"), i, 2)
        browser_layout.addWidget(self.utterance_box, i + 1, 2)
        self.browser_load_button = QPushButton("Load")
        browser_layout.addWidget(self.browser_load_button, i + 1, 3)
        i += 2

        # Random buttons
        self.random_dataset_button = QPushButton("Random")
        browser_layout.addWidget(self.random_dataset_button, i, 0)
        self.random_speaker_button = QPushButton("Random")
        browser_layout.addWidget(self.random_speaker_button, i, 1)
        self.random_utterance_button = QPushButton("Random")
        browser_layout.addWidget(self.random_utterance_button, i, 2)
        self.auto_next_checkbox = QCheckBox("Auto select next")
        self.auto_next_checkbox.setChecked(True)
        browser_layout.addWidget(self.auto_next_checkbox, i, 3)
        i += 1

        # Utterance box
        browser_layout.addWidget(QLabel("<b>Use embedding from:</b>"), i, 0)
        self.utterance_history = QComboBox()
        browser_layout.addWidget(self.utterance_history, i, 1, 1, 3)
        i += 1

        # Random & next utterance buttons
        self.browser_browse_button = QPushButton("Browse")
        browser_layout.addWidget(self.browser_browse_button, i, 0)
        self.record_button = QPushButton("Record")
        browser_layout.addWidget(self.record_button, i, 1)
        self.play_button = QPushButton("Play")
        browser_layout.addWidget(self.play_button, i, 2)
        self.stop_button = QPushButton("Stop")
        browser_layout.addWidget(self.stop_button, i, 3)
        i += 1


        # Model and audio output selection
        self.speaker_encoder_box = QComboBox()
        browser_layout.addWidget(QLabel("<b>Speaker Encoder</b>"), i, 0)
        browser_layout.addWidget(self.speaker_encoder_box, i + 1, 0)
        self.emotion_encoder_box = QComboBox()
        browser_layout.addWidget(QLabel("<b>Emotion Encoder</b>"), i, 1)
        browser_layout.addWidget(self.emotion_encoder_box, i + 1, 1)
        self.synthesizer_box = QComboBox()
        browser_layout.addWidget(QLabel("<b>Synthesizer</b>"), i, 2)
        browser_layout.addWidget(self.synthesizer_box, i + 1, 2)
        self.vocoder_box = QComboBox()
        browser_layout.addWidget(QLabel("<b>Vocoder</b>"), i, 3)
        browser_layout.addWidget(self.vocoder_box, i + 1, 3)

        self.audio_out_devices_cb=QComboBox()
        browser_layout.addWidget(QLabel("<b>Audio Output</b>"), i, 4)
        browser_layout.addWidget(self.audio_out_devices_cb, i + 1, 4)
        i += 2

        #Replay & Save Audio
        browser_layout.addWidget(QLabel("<b>Toolbox Output:</b>"), i, 0)
        self.waves_cb = QComboBox()
        self.waves_cb_model = QStringListModel()
        self.waves_cb.setModel(self.waves_cb_model)
        self.waves_cb.setToolTip("Select one of the last generated waves in this section for replaying or exporting")
        browser_layout.addWidget(self.waves_cb, i, 1)
        self.replay_wav_button = QPushButton("Replay")
        self.replay_wav_button.setToolTip("Replay last generated vocoder")
        browser_layout.addWidget(self.replay_wav_button, i, 2)
        self.export_wav_button = QPushButton("Export")
        self.export_wav_button.setToolTip("Save last generated vocoder audio in filesystem as a wav file")
        browser_layout.addWidget(self.export_wav_button, i, 3)
        i += 1


        ## Embed & spectrograms
        # vis_layout.addStretch()

        gridspec_kw = {"width_ratios": [1, 1, 2]}
        self.wav_ori_fig, self.current_ax = plt.subplots(1, 3, figsize=(6, 2.25), facecolor="#F0F0F0",
                                            gridspec_kw=gridspec_kw)
        self.wav_ori_fig.subplots_adjust(left=0, bottom=0.1, right=1, top=0.8)
        vis_layout.addWidget(FigureCanvas(self.wav_ori_fig))

        self.wav_gen_fig, self.gen_ax = plt.subplots(1, 3, figsize=(6, 2.25), facecolor="#F0F0F0",
                                        gridspec_kw=gridspec_kw)
        self.wav_gen_fig.subplots_adjust(left=0, bottom=0.1, right=1, top=0.8)
        vis_layout.addWidget(FigureCanvas(self.wav_gen_fig))

        for ax in self.current_ax.tolist() + self.gen_ax.tolist():
            ax.set_facecolor("#F0F0F0")
            for side in ["top", "right", "bottom", "left"]:
                ax.spines[side].set_visible(False)


        ## Generation
        self.text_prompt = QPlainTextEdit(default_text)
        gen_layout.addWidget(self.text_prompt)

        self.generate_button = QPushButton("Synthesize and vocode")
        gen_layout.addWidget(self.generate_button)

        layout = QHBoxLayout()
        self.synthesize_button = QPushButton("Synthesize only")
        layout.addWidget(self.synthesize_button)
        self.vocode_button = QPushButton("Vocode only")
        layout.addWidget(self.vocode_button)
        gen_layout.addLayout(layout)

        layout_seed = QGridLayout()
        self.random_seed_checkbox = QCheckBox("Random seed:")
        self.random_seed_checkbox.setToolTip("When checked, makes the synthesizer and vocoder deterministic.")
        layout_seed.addWidget(self.random_seed_checkbox, 0, 0)
        self.seed_textbox = QLineEdit()
        self.seed_textbox.setMaximumWidth(80)
        layout_seed.addWidget(self.seed_textbox, 0, 1)
        self.trim_silences_checkbox = QCheckBox("Enhance vocoder output")
        self.trim_silences_checkbox.setChecked(False)
        self.trim_silences_checkbox.setToolTip("When checked, trims excess silence in vocoder output."
            " This feature requires `webrtcvad` to be installed.")
        layout_seed.addWidget(self.trim_silences_checkbox, 0, 2)
        self.griffin_lim_checkbox = QCheckBox("Griffin-Lim as vocoder")
        self.griffin_lim_checkbox.setChecked(False)
        self.griffin_lim_checkbox.setToolTip("When checked, Griffin-Lim is vocoder.")
        layout_seed.addWidget(self.griffin_lim_checkbox, 0, 3)
        gen_layout.addLayout(layout_seed)

        self.loading_bar = QProgressBar()
        gen_layout.addWidget(self.loading_bar)

        self.log_window = QLabel()
        self.log_window.setAlignment(Qt.AlignBottom | Qt.AlignLeft)
        gen_layout.addWidget(self.log_window)
        self.logs = []
        # gen_layout.addStretch()


        ## Set the size of the window and of the elements
        max_size = QDesktopWidget().availableGeometry(self).size() * 0.8
        self.resize(max_size)

        ## Finalize the display
        self.reset_interface()
        self.show()

    def start(self):
        self.app.exec_()
