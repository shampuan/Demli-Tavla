#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import random
import json
import time
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, 
                             QHBoxLayout, QLabel, QPushButton, QMenuBar, 
                             QMenu, QAction, QMessageBox, QTextEdit,
                             QGraphicsOpacityEffect)
from PyQt5.QtGui import QPixmap, QIcon, QFont, QMovie, QTransform
from PyQt5.QtCore import Qt, QTimer, QPoint
import pygame
from tavla_ai import TavlaAI
from tavla_ai_flipped import TavlaAIFlipped

# Linux/Debian tabanlı sistemler için X11 zorlaması
os.environ["QT_QPA_PLATFORM"] = "xcb"

class ScoreWindow(QMessageBox):
    def __init__(self, kazanan, puan, sure, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Oyun Bitti - Skor Tablosu")
        
        dakika = int(sure // 60)
        saniye = int(sure % 60)
        sure_str = f"{dakika:02d}:{saniye:02d}"
        
        skor_metni = (
            f"KAZANAN: {kazanan}\n"
            f"PUAN   : {puan} (Mars: {'Evet' if puan == 2 else 'Hayır'})\n"
            f"SÜRE   : {sure_str}"
        )
        
        self.setText("Oyun Bitti!")
        self.setInformativeText(skor_metni)
        self.setStandardButtons(QMessageBox.Ok)

class Pul(QLabel):
    def __init__(self, parent, renk, dosya_yolu, x_coords, y_top, y_bottom, main_window):
        super().__init__(parent)
        self.renk = renk
        self.x_coords = x_coords
        self.y_top = y_top
        self.y_bottom = y_bottom
        self.main_window = main_window
        self.current_hane = None
        self.old_pos = QPoint()
        self.old_hane = None
        
        pix = QPixmap(dosya_yolu)
        self.setPixmap(pix.scaled(43, 43, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.setFixedSize(43, 43)
        self.setCursor(Qt.OpenHandCursor)
        self.moving = False

    def mousePressEvent(self, event):
        # Önce oyunun duraklatılıp duraklatılmadığını veya bitip bitmediğini kontrol ediyoruz ki sapıtmasın
        if not self.main_window.game_started: return # Oyun bittiyse hareket etme dur ve öyle kal
        if self.main_window.is_paused: return
        
        if event.button() == Qt.LeftButton:
            # Zar atılma ve sıra kontrolü
            if not self.main_window.dice_rolled: return
            if self.renk != self.main_window.turn: return
            # Kırık pul varken tahtadaki pulu oynatma yasağı
            if len(self.main_window.kirik_pullar[self.renk]) > 0 and self.current_hane != -1: return
    
            # Sürükleme başladığında oyuncunun kullandığı değişkenlerin atanması
            self.moving = True
            self.old_pos = self.pos()
            self.old_hane = -1 if self.current_hane == -1 and self.renk == "Acik" else (24 if self.current_hane == -1 else self.current_hane)
            self.offset = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            self.raise_()

    def mouseMoveEvent(self, event):
        if self.moving:
            self.move(self.mapToParent(event.pos() - self.offset))

    def mouseReleaseEvent(self, event):
        if self.moving:
            self.moving = False
            self.setCursor(Qt.OpenHandCursor)
            self.snap_to_grid()
            
    def mouseDoubleClickEvent(self, event):
        if self.main_window.is_paused or not self.main_window.dice_rolled: return
        if self.renk != self.main_window.turn: return
        
        # Sadece toplama aşamasındaysak çift tıklama çalışsın 
        if self.main_window.is_all_in_home(self.renk):
            self.attempt_bear_off()
            
    def attempt_bear_off(self):
        """Pulu çift tıklama ile dışarı atmaya çalışır."""
        dist_to_exit = (24 - self.current_hane) if self.renk == "Acik" else (self.current_hane + 1)
        
        # En uzaktaki pulu bul (daha büyük zarla toplama kuralı için)
        max_dist = 0
        for p_check in self.main_window.pullar:
            if p_check.renk == self.renk:
                d = (24 - p_check.current_hane) if self.renk == "Acik" else (p_check.current_hane + 1)
                if d > max_dist: max_dist = d

        # Uygun zar var mı?
        available_dice = [d for d in self.main_window.available_moves if d == dist_to_exit]
        if not available_dice and dist_to_exit == max_dist:
            available_dice = [d for d in self.main_window.available_moves if d > dist_to_exit]

        if available_dice:
            chosen_dice = min(available_dice)
            self.main_window.available_moves.remove(chosen_dice)
            
            # Tahtadan kaldır
            if 0 <= self.current_hane <= 23:
                if self in self.main_window.board_state[self.current_hane]:
                    self.main_window.board_state[self.current_hane].remove(self)
            
            self.main_window.pullar.remove(self)
            self.hide()
            
            # Arayüzü ve oyun durumunu güncelle
            self.main_window.update_moves_display()
            self.main_window.check_win_condition(self.renk)
            if not self.main_window.available_moves or not self.main_window.check_any_legal_move():
                self.main_window.end_turn()

    def snap_to_grid(self):
        curr_x = self.x() + 21
        curr_y = self.y() + 21
        
        # En yakın X çizgisini bul
        closest_x = min(self.x_coords, key=lambda x: abs(x - curr_x))
        x_idx = self.x_coords.index(closest_x)
        is_top = curr_y < 234

        # AYNALI HESAPLAMA - burası tahtayı ters yüz ettiğimizde gerekli olacak
        if self.main_window.is_flipped:
            # Ters düzen: X indeksi hane numarasının kendisine eşittir
            new_hane = x_idx if is_top else 23 - x_idx
        else:
            # Standart düzen:
            new_hane = 11 - x_idx if is_top else 12 + x_idx

        can_bear_off = self.main_window.is_all_in_home(self.renk)
        is_collecting = False
        dist_to_exit = 0

        if can_bear_off:
            if self.renk == "Acik" and (self.x() + 21) > 520:
                is_collecting = True
                dist_to_exit = 24 - self.old_hane
            elif self.renk == "Koyu" and (self.x() + 21) < 80:
                is_collecting = True
                dist_to_exit = self.old_hane + 1

        if is_collecting:
            max_dist = 0
            for p_check in self.main_window.pullar:
                if p_check.renk == self.renk:
                    d = (24 - p_check.current_hane) if self.renk == "Acik" else (p_check.current_hane + 1)
                    if d > max_dist: max_dist = d

            available_dice = [d for d in self.main_window.available_moves if d == dist_to_exit]
            if not available_dice and dist_to_exit == max_dist:
                available_dice = [d for d in self.main_window.available_moves if d > dist_to_exit]

            if available_dice:
                chosen_dice = min(available_dice)
                self.main_window.available_moves.remove(chosen_dice)
                self.main_window.update_moves_display() # Pul toplandı, yazıyı güncelle!
                if self.old_hane is not None and 0 <= self.old_hane <= 23:
                    if self in self.main_window.board_state[self.old_hane]:
                        self.main_window.board_state[self.old_hane].remove(self)
                self.main_window.pullar.remove(self)
                self.hide()
                
                rem = [p for p in self.main_window.pullar if p.renk == self.renk]
                if not rem:
                    toplam_sure = time.time() - self.main_window.start_time
                    rakip_puan = 2 if len([p for p in self.main_window.pullar if p.renk != self.renk]) == 15 else 1
                    kazanan_isim = "Beyaz" if self.renk == "Acik" else "Siyah"
                    
                    self.main_window.play_jingle("mirkelam_win.mp3", self.main_window.vol_mirkelam_win)
                    self.main_window.save_score(kazanan_isim, rakip_puan, toplam_sure)
                    
                    skor_penceresi = ScoreWindow(kazanan_isim, rakip_puan, toplam_sure, self.main_window)
                    skor_penceresi.exec_()
                    
                    self.main_window.btn_roll.setEnabled(False)
                    self.main_window.dice_rolled = True
                    self.main_window.turn_text_label.setText(f"KAZANAN: {kazanan_isim}")
                elif not self.main_window.available_moves or not self.main_window.check_any_legal_move():
                    self.main_window.end_turn()
                return

        if self.renk == "Acik": distance = new_hane - self.old_hane
        else: distance = self.old_hane - new_hane

        is_valid_direction = distance > 0
        is_valid_distance = distance in self.main_window.available_moves
        target_hane_content = self.main_window.board_state[new_hane]
        is_blocked = (len(target_hane_content) >= 2 and target_hane_content[0].renk != self.renk)

        if is_valid_direction and is_valid_distance and not is_blocked:
            self.main_window.save_for_undo()
            self.main_window.available_moves.remove(distance)
            self.main_window.update_moves_display() # Hamle yapıldı, yazıyı güncelle!
            if self.old_hane in [-1, 24] and self in self.main_window.kirik_pullar[self.renk]:
                self.main_window.kirik_pullar[self.renk].remove(self)
            if len(target_hane_content) == 1 and target_hane_content[0].renk != self.renk:
                kirilan = target_hane_content.pop(0)
                self.main_window.kirik_pullar[kirilan.renk].append(kirilan)
                kirilan.move(self.main_window.bar_x - 21, (self.main_window.bar_y_top if kirilan.renk == "Koyu" else self.main_window.bar_y_bottom) - 21)
                kirilan.current_hane = -1 
            if 0 <= self.old_hane <= 23 and self in self.main_window.board_state[self.old_hane]:
                self.main_window.board_state[self.old_hane].remove(self)
            self.current_hane = new_hane
            self.main_window.board_state[new_hane].append(self)
            h_cnt = self.main_window.board_state[new_hane].index(self)
            target_y = (self.y_top if is_top else self.y_bottom)[min(h_cnt, 4)]
            self.move(closest_x - 21, target_y - 21)
            if not self.main_window.available_moves or not self.main_window.check_any_legal_move():
                self.main_window.end_turn()
        else:
            self.move(self.old_pos)

class DemliTavla(QMainWindow):
    def __init__(self):
        super().__init__()
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.config_dir = os.path.join(os.path.expanduser("~"), ".config", "DemliTavla")
        if not os.path.exists(self.config_dir): os.makedirs(self.config_dir)
        self.scores_file = os.path.join(self.config_dir, "skorlar.json")
        
        # Temel Değişkenler (koordinatlar ve diğer durumlar)
        self.x_points = [31, 72, 110, 151, 191, 232, 301, 341, 382, 421, 462, 502]
        self.y_top_points = [30, 69, 108, 147, 186]
        self.y_bottom_points = [438, 398, 358, 319, 280]
        self.board_state = {i: [] for i in range(24)}
        self.available_moves = []
        self.undo_stack = []
        self.dice_rolled = False
        self.is_flipped = False
        self.game_started = False
        self.game_over = False
        self.is_paused = False
        self.start_time = 0
        self.turn = "Acik"
        self.pullar = []
        self.kirik_pullar = {"Acik": [], "Koyu": []}
        self.bar_x, self.bar_y_top, self.bar_y_bottom = 266, 150, 300
        
        # Ses Ayarları - ayarları böyle bırakıyorum böyle iyi. mirkelam için teliften dolayı midi'ye geçtim. 
        pygame.mixer.init()
        self.vol_kahve_ortam, self.vol_zar_sallama, self.vol_zar_durma = 0.08, 0.8, 0.5
        self.vol_mirkelam_giris, self.vol_mirkelam_win = 0.4, 0.4
        self.chan_ambient = pygame.mixer.Channel(0)
        self.chan_effects = pygame.mixer.Channel(1)
        self.chan_music = pygame.mixer.Channel(2)

        # AI Başlatma
        self.ai_player = TavlaAI("Koyu") # gerekli importu ekledim.

        # Arayüzü Başlat (En Son)
        self.init_ui()
        self.loop_ambient("kıraathane.mp3")
        self.play_jingle("mirkelam_tavla.mp3", self.vol_mirkelam_giris)
        
    def check_win_condition(self, renk):
        rem = [p for p in self.pullar if p.renk == renk]
        if not rem:
            toplam_sure = time.time() - self.start_time
            rakip_puan = 2 if len([p for p in self.pullar if p.renk != renk]) == 15 else 1
            kazanan_isim = "Beyaz" if renk == "Acik" else "Siyah"
            
            self.play_jingle("mirkelam_win.mp3", self.vol_mirkelam_win)
            self.save_score(kazanan_isim, rakip_puan, toplam_sure)
            
            # --- OYUN BİTTİYSE DÜĞMELER PASİF ---
            if hasattr(self, 'dice_timer'):
                self.dice_timer.stop()  # Yanıp sönmeyi sağlayan beyni durdurur
            self.btn_roll.setEnabled(False) # Butonu pasif yapar
            # -------------------------------

            from PyQt5.QtWidgets import QMessageBox
            skor_penceresi = ScoreWindow(kazanan_isim, rakip_puan, toplam_sure, self)
            skor_penceresi.exec_()
            
            self.game_started = False
            self.game_over = True
            self.dice_rolled = True

    def get_path(self, filename): return os.path.join(self.base_path, filename)
    def loop_ambient(self, filename):
        path = self.get_path(filename)
        if os.path.exists(path):
            s = pygame.mixer.Sound(path)
            s.set_volume(self.vol_kahve_ortam)
            self.chan_ambient.play(s, loops=-1)
    def play_effect(self, filename, volume):
        path = self.get_path(filename)
        if os.path.exists(path):
            s = pygame.mixer.Sound(path)
            s.set_volume(volume)
            self.chan_effects.play(s)
    def play_jingle(self, filename, volume):
        path = self.get_path(filename)
        if os.path.exists(path):
            s = pygame.mixer.Sound(path)
            s.set_volume(volume)
            self.chan_music.play(s)

    def init_ui(self):
        self.setWindowTitle("Demli Tavla")
        self.setWindowIcon(QIcon(self.get_path("tavlaicon.png")))
        self.setFixedSize(800, 525)
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QHBoxLayout()
        self.central_widget.setLayout(self.main_layout)

        # Oyun Alanı
        self.board_area = QWidget()
        self.board_area.setFixedSize(533, 468)
        self.board_img = QLabel(self.board_area)
        self.board_img.setPixmap(QPixmap(self.get_path("tavla.png")))
        self.board_img.setFixedSize(533, 468)
        self.board_img.setScaledContents(True)
        self.main_layout.addWidget(self.board_area)

        # Sağ Panel (Kontroller)
        self.side_panel = QVBoxLayout()

        # --- GÖRSEL SIRA GÖSTERGESİ ---
        self.status_container = QWidget()
        self.status_layout = QVBoxLayout(self.status_container) # QH idi, QV (Dikey) yaptık ki alt alta düzgün dursun
        self.status_layout.setContentsMargins(0, 0, 0, 0)
        
        # Üst satır: Sıra yazısı ve Pul
        self.top_row = QHBoxLayout()
        self.turn_text_label = QLabel("Sıra:")
        self.turn_text_label.setFont(QFont("Liberation Sans", 11, QFont.Bold))
        self.status_image_label = QLabel()
        self.top_row.addWidget(self.turn_text_label)
        self.top_row.addWidget(self.status_image_label) # yanına da pul resmi koyduk mu tamam.
        self.top_row.addStretch()
        
        # Alt satır: Kalan hamleler (Zar bilgisi)
        self.moves_label = QLabel("")
        self.moves_label.setFont(QFont("Liberation Sans", 11, QFont.StyleItalic))
        self.moves_label.setStyleSheet("color: #0000ff;") # şimdilik mavi iyidir.
        
        self.status_layout.addLayout(self.top_row)
        self.status_layout.addWidget(self.moves_label)
        
        self.side_panel.addWidget(self.status_container)

        # Zarlar
        self.dice_layout = QHBoxLayout()
        self.d1 = QLabel()
        self.d2 = QLabel()
        self.set_dice(self.d1, 1)
        self.set_dice(self.d2, 1)
        self.dice_layout.addWidget(self.d1)
        self.dice_layout.addWidget(self.d2)
        self.dice_layout.addStretch() # Zarları sola yaslar ilerde ortalayabilirim de. Şimdilik kalsın.
        self.side_panel.addLayout(self.dice_layout)

       # Butonlar Kontrolü
        self.controls_layout = QVBoxLayout()
        self.button_row_layout = QHBoxLayout()
        
        self.btn_roll = QPushButton("Zarı At")
        self.btn_roll.setFont(QFont("Liberation Sans"))
        self.btn_roll.setFixedHeight(40)
        self.btn_roll.clicked.connect(self.roll_dice_anim)
        
        self.btn_undo = QPushButton("Geri Al")
        self.btn_undo.setFont(QFont("Liberation Sans"))
        self.btn_undo.setFixedHeight(40)
        self.btn_undo.clicked.connect(self.undo_move)
        
        self.button_row_layout.addWidget(self.btn_roll, 2)
        self.button_row_layout.addWidget(self.btn_undo, 1)
        self.controls_layout.addLayout(self.button_row_layout)

        self.btn_flip = QPushButton("Tahtayı Ters Çevir")
        self.btn_flip.setFont(QFont("Liberation Sans"))
        self.btn_flip.setFixedHeight(30)
        self.btn_flip.clicked.connect(self.flip_board)
        self.controls_layout.addWidget(self.btn_flip)
        self.side_panel.addLayout(self.controls_layout)
        
        # Çay Animasyonu
        self.cay_label = QLabel()
        self.cay_label.setFixedSize(240, 240)  # Taşmayı önlemek için boyut sabitlendi bu da tamam buna ellenmeyecek.
        self.cay_label.setAlignment(Qt.AlignCenter)
        self.cay_movie = QMovie(self.get_path("turkish_cay.gif")) # umarım trt telif atmaz. Başka adam akıllı çay gifi yok. 
        self.cay_movie.setScaledSize(self.cay_label.size()) # Gifi etikete sığdır
        self.cay_label.setMovie(self.cay_movie)
        self.cay_movie.start()

        # Side panel yerleşimi (Çay en üstte, sonra butonlar)
        self.side_panel.addWidget(self.cay_label) # Gifi en tepeye aldık ve boşlukları dengeledik bu da bitti. 
        self.side_panel.addWidget(self.btn_roll)
        self.side_panel.addWidget(self.btn_flip)
        self.side_panel.addStretch()
        self.main_layout.addLayout(self.side_panel)
        
        self.create_menu()
        self.setup_visual_board()
        self.update_turn_visual() 
        self.central_widget.setLayout(self.main_layout)
        
    def save_for_undo(self):
        """Durumu tam kopya olarak dondurur. çünkü devam dediğimde programın veriye ihtiyacı var. """
        saved_board = {h: list(p_list) for h, p_list in self.board_state.items()}
        pul_haneleri = {p: p.current_hane for p in self.pullar}
        state = {
            'board': saved_board,
            'moves': list(self.available_moves),
            'kirik': {r: list(p_list) for r, p_list in self.kirik_pullar.items()},
            'pul_positions': pul_haneleri
        }
        self.undo_stack.append(state)
        
    def undo_move(self):
        """Hafızadaki son durumu geri yükler ve tahta yönüne göre pulları dizer."""
        if not self.undo_stack or self.is_paused: return
        
        last_state = self.undo_stack.pop()
        self.board_state = last_state['board']
        self.available_moves = last_state['moves']
        self.kirik_pullar = last_state['kirik']
        
        # 1. Pulların mantıksal hane bilgilerini geri yükler
        for pul, hane in last_state['pul_positions'].items():
            pul.current_hane = hane
            
        # 2. Tahtadaki pulları görsel olarak yerlerine taşır
        for h_id, pullar_listesi in self.board_state.items():
            for i, p in enumerate(pullar_listesi):
                # Tahta tersse, hane ID'sini koordinat sistemine göre simetriğine çeviriyoruz
                # Çünkü x_points ve y_points listelerin sabit, ama hane dizilimi değişiyor.
                is_top = h_id <= 11
                
                if self.is_flipped:
                    # Ters düzende: 0-11 aşağıda, 12-23 yukarıda gibi düşünülmeli. 
                    # Sistemi buna göre kuruyoruz. 
                    x_idx = h_id if is_top else 23 - h_id
                else:
                    x_idx = 11 - h_id if is_top else h_id - 12
                
                target_x = self.x_points[x_idx]
                y_list = self.y_top_points if is_top else self.y_bottom_points
                
                # update_pul_visual_pos kullanmak yerine doğrudan burada hesaplıyoruz ki
                # çapraz kaymaları engelleyelim.
                p.move(int(target_x) - 21, y_list[min(i, 4)] - 21)
                p.show()
        
        # 3. Kırık pulları bara geri taşı
        for renk, pullar_listesi in self.kirik_pullar.items():
            for p in pullar_listesi:
                p.move(self.bar_x - 21, (self.bar_y_top if p.renk == "Koyu" else self.bar_y_bottom) - 21)
                p.show()

        # 4. Arayüz güncellemeleri
        self.dice_rolled = True
        self.btn_roll.setEnabled(False) 
        self.update_moves_display()
        self.update_turn_visual()

    def update_turn_visual(self):
        """Sıradaki oyuncunun pulunu sağ panelde gösterir."""
        dosya = "pul_acik.png" if self.turn == "Acik" else "pul_koyu.png"
        pix = QPixmap(self.get_path(dosya))
        if not pix.isNull():
            # Sıranın kimde olduğunu pulla gösteriyoruz artıkın.
            self.status_image_label.setPixmap(pix.scaled(45, 45, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def update_moves_display(self):
        """Kalan hamleleri gösterir ve hamle bittiğinde zarları soluklaştırır/geri alı kilitler."""
        if not self.available_moves:
            self.moves_label.setText("")
            # Hamle kalmadıysa zarları soluklaştırma fonksiyonu aklımı seveyim.
            self.d1.setGraphicsEffect(self.get_opacity_effect(0.3))
            self.d2.setGraphicsEffect(self.get_opacity_effect(0.3))
            
            # --- EKLEDİĞİMİZ KİLİT ---
            self.btn_undo.setEnabled(False)
            self.undo_stack = [] # Hamle bittiği için geçmişi temizle
            # -------------------------
        else:
            hamleler = ", ".join(map(str, self.available_moves))
            self.moves_label.setText(f"Hamleler: {hamleler}")
            # Hamle varken zarlar parlak olsun
            self.d1.setGraphicsEffect(None)
            self.d2.setGraphicsEffect(None)
            
            # --- GERİ AL AKTİFLEŞTİRME ---
            # Sadece Beyaz (İnsan) oyuncunun sırasındaysa geri al aktif kalsın
            if self.turn == "Acik":
                self.btn_undo.setEnabled(True)
            
    def get_opacity_effect(self, value):
        """Görsel öğeler için şeffaflık efekti oluşturur."""
        effect = QGraphicsOpacityEffect()
        effect.setOpacity(value)
        return effect

    def create_menu(self):
        m = self.menuBar()
        g = m.addMenu("Oyun")
        g.addAction(QAction("Yeni Oyun", self, triggered=self.new_game))
        g.addSeparator()
        self.action_pause = QAction("Oyunu Dondur", self, triggered=self.pause_game)
        self.action_resume = QAction("Devam Et", self, triggered=self.resume_game)
        self.action_resume.setEnabled(False)
        g.addAction(self.action_pause); g.addAction(self.action_resume)
        g.addSeparator()
        g.addAction(QAction("Skor Geçmişi", self, triggered=self.show_scores))
        g.addSeparator()
        g.addAction(QAction("Kapat", self, triggered=self.close))
        h = m.addMenu("Hakkında")
        h.addAction(QAction("Hakkında", self, triggered=self.show_about))

    def setup_visual_board(self):
        # Standart diziliş (Hane ID, Adet, Renk)
        placements = [
            (0, 2, "Acik"), (5, 5, "Koyu"), (7, 3, "Koyu"), (11, 5, "Acik"),
            (12, 5, "Koyu"), (16, 3, "Acik"), (18, 5, "Acik"), (23, 2, "Koyu")
        ]

        for h_id, adet, renk in placements:
            # KRİTİK NOKTA: Sadece X eksenini aynalıyoruz (Kale sağdan sola geçer)
            # is_top (Üst sıra 0-11, Alt sıra 12-23) mantığı SABİT KALIR.
            is_top = h_id <= 11
            
            if self.is_flipped:
                # Normalde 11-h_id olan x_idx'i tam tersine çeviriyoruz
                x_idx = h_id if is_top else 23 - h_id
            else:
                x_idx = 11 - h_id if is_top else h_id - 12
            
            target_x = self.x_points[x_idx]
            y_list = self.y_top_points if is_top else self.y_bottom_points
            
            dosya = self.get_path("pul_acik.png") if renk == "Acik" else self.get_path("pul_koyu.png")
            
            for i in range(adet):
                p = Pul(self.board_area, renk, dosya, self.x_points, self.y_top_points, self.y_bottom_points, self)
                p.current_hane = h_id # Mantıksal ID değişmez
                self.board_state[h_id].append(p)
                p.move(int(target_x) - 21, y_list[min(i, 4)] - 21)
                p.show()
                self.pullar.append(p)

    def set_dice(self, label, val):
        pix = QPixmap(self.get_path(f"dice_{val}.png"))
        label.setPixmap(pix.scaled(72, 72, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def roll_dice_anim(self):
        self.undo_stack = [] # Yeni tur başlayınca eski geçmişi temizletme şeysi.
        if not self.game_started and hasattr(self, 'game_over') and self.game_over: return 
        if self.dice_rolled or self.is_paused: return
        if self.dice_rolled or self.is_paused: return
        self.undo_stack = []
        self.d1.setGraphicsEffect(None)
        self.d2.setGraphicsEffect(None)
        self.btn_roll.setEnabled(False)
        if not self.game_started:
            self.game_started = True; self.start_time = time.time(); self.btn_flip.setEnabled(False)
        self.play_effect("dices_shaking.mp3", self.vol_zar_sallama)
        self.r_cnt = 0; self.t = QTimer(); self.t.timeout.connect(self.anim_step); self.t.start(80)

    def anim_step(self):
        v1, v2 = random.randint(1, 6), random.randint(1, 6)
        self.set_dice(self.d1, v1); self.set_dice(self.d2, v2)
        self.r_cnt += 1
        if self.r_cnt > 12:
            self.t.stop(); self.play_effect("dices_stopped.mp3", self.vol_zar_durma)
            self.dice_rolled = True
            self.available_moves = [v1, v1, v1, v1] if v1 == v2 else [v1, v2]
            self.update_moves_display() 
            
            if not self.check_any_legal_move():
                if self.turn == "Acik": # Sadece insan oyuncuya mesaj göster
                    QMessageBox.information(self, "Bilgi", "Gele! Sıra Karşıda.")
                self.end_turn()
            else:
                # EĞER SIRA AI'DAYSA HAMLE YAPMAYA BAŞLA
                if self.turn == "Koyu":
                    QTimer.singleShot(600, self.execute_ai_move)
    
    def check_any_legal_move(self):
        if not self.available_moves: return False
        pullar = [p for p in self.pullar if p.renk == self.turn]
        can_bear = self.is_all_in_home(self.turn)
        max_d = max([(24-p.current_hane if p.renk=="Acik" else p.current_hane+1) for p in pullar]) if can_bear and pullar else 0
        for p in pullar:
            if len(self.kirik_pullar[self.turn]) > 0 and p.current_hane != -1: continue
            for m in set(self.available_moves):
                start = p.current_hane if p.current_hane != -1 else (-1 if p.renk=="Acik" else 24)
                target = start + m if p.renk=="Acik" else start - m
                dist = 24 - start if p.renk=="Acik" else start + 1
                if 0 <= target <= 23:
                    cont = self.board_state[target]
                    if not (len(cont) >= 2 and cont[0].renk != p.renk): return True
                elif can_bear and (m == dist or (m > dist and dist == max_d)): return True
        return False

    def is_all_in_home(self, renk):
        home = range(18, 24) if renk == "Acik" else range(0, 6)
        return all(p.current_hane in home for p in self.pullar if p.renk == renk)
    
    def is_all_home(self, renk): return self.is_all_in_home(renk)
    
    def end_turn(self):
        self.dice_rolled = False
        self.available_moves = [] # Hamleleri sıfırla
        self.update_moves_display() # Yazıyı temizle
        self.turn = "Koyu" if self.turn == "Acik" else "Acik"
        self.update_turn_visual() 
        
        if not self.is_paused:
            # Eğer sıra Beyaz'daysa (İnsan), butonu aktifleştir ve parlat
            if self.turn == "Acik":
                self.btn_roll.setEnabled(True)
                self.blink_roll_button()
            
            # Eğer sıra Koyu'daysa (AI) ve oyun devam ediyorsa, AI'yı başlat
            elif self.turn == "Koyu" and self.game_started:
                self.btn_roll.setEnabled(False) # AI oynarken butonu kapat
                QTimer.singleShot(600, self.run_ai_turn) # 1 saniye sonra AI zar atar
        
    def blink_roll_button(self):
        # Yanıp sönme efektini yöneten iç fonksiyon
        self.blink_count = 0
        self.blink_timer = QTimer(self)
        
        def toggle_style():
            if self.blink_count < 8:  # 4 kez yanıp sönme (aç-kapat toplam 8 adım)
                if self.blink_count % 2 == 0:
                    # Parlak yeşil arka plan ve beyaz yazı
                    self.btn_roll.setStyleSheet("background-color: #1b821b; color: white; font-weight: bold;")
                else:
                    # Eski haline döndür (varsayılan stil)
                    self.btn_roll.setStyleSheet("")
                
                self.blink_count += 1
            else:
                self.blink_timer.stop()
                self.btn_roll.setStyleSheet("") # En son temizle

        self.blink_timer.timeout.connect(toggle_style)
        self.blink_timer.start(150) # 150ms aralıklı yanıp sönsün

    def pause_game(self):
        # Oyun başlamadıysa veya zaten dondurulmuşsa işlem yapma
        if not self.game_started or self.is_paused: 
            return
            
        self.is_paused = True
        self.pause_start = time.time() # Duraklatma anını kaydet ki daha sonra kaldığı yerden devam etsin.
        
        # Menü ve buton kontrolleri
        self.action_pause.setEnabled(False)
        self.action_resume.setEnabled(True)
        self.btn_roll.setEnabled(False)
        self.btn_undo.setEnabled(False)
        
        # Durum yazısını güncelle (Hatalı status_label yerine turn_text_label kullanıldı)
        self.turn_text_label.setText("DONDURULDU")
        
        # Pulların tıklanabilirliğini kapat
        for p in self.pullar: 
            p.setAttribute(Qt.WA_TransparentForMouseEvents, True)

    def resume_game(self):
        if not self.is_paused: 
            return
            
        self.is_paused = False
        # Geçen süreyi ana süreden çıkararak oyun süresini doğru hesaplamak için formül.
        self.start_time += (time.time() - self.pause_start)
        
        # Menü ve butonları eski haline getir
        self.action_pause.setEnabled(True)
        self.action_resume.setEnabled(False)
        
        # Pulların tıklanabilirliğini tekrar aç
        for p in self.pullar: 
            p.setAttribute(Qt.WA_TransparentForMouseEvents, False)

        # DURUM KONTROLÜ VE AI TETİKLEME
        if self.turn == "Acik":
            # Sıra insandaysa ve zar atılmadıysa butonu aç
            if not self.dice_rolled:
                self.btn_roll.setEnabled(True)
            self.btn_undo.setEnabled(True)
            self.turn_text_label.setText("Sıra:")
            self.update_turn_visual()
        else:
            # Sıra AI'daysa (Koyu)
            self.btn_roll.setEnabled(False)
            self.btn_undo.setEnabled(False)
            self.turn_text_label.setText("Sıra:")
            self.update_turn_visual()
            
            # Eğer zar atılmış ve hamle bekliyorsa hamle yap, zar atılmamışsa zar at
            if self.dice_rolled:
                if self.available_moves:
                    QTimer.singleShot(500, self.execute_ai_move)
                else:
                    self.end_turn()
            else:
                QTimer.singleShot(500, self.run_ai_turn)

    def new_game(self):
        # Mevcut pulları temizle
        for p in self.pullar: 
            p.deleteLater()
        
        # Değişkenleri ilk hallerine döndür
        self.pullar = []
        self.board_state = {i: [] for i in range(24)}
        self.kirik_pullar = {"Acik": [], "Koyu": []}
        self.available_moves = []
        self.undo_stack = []
        
        # Oyun durumu ve kilitleri sıfırla
        self.dice_rolled = False
        self.game_started = False
        self.is_paused = False
        self.game_over = False  # Zar atma kilidini kaldırıyoruz
        self.turn = "Acik"
        
        # Arayüzü güncelle
        self.turn_text_label.setText("Sıra:")
        self.moves_label.setText("")
        self.btn_roll.setEnabled(True)
        self.btn_flip.setEnabled(True)
        self.action_pause.setEnabled(True)
        self.action_resume.setEnabled(False)
        self.update_turn_visual()
        
        # Tahtayı ve sesleri başlat
        self.setup_visual_board()
        self.play_jingle("mirkelam_tavla.mp3", self.vol_mirkelam_giris) # orjinal sesi teliften dolayı değiştirdim.
    def save_score(self, kazanan, puan, sure):
        yeni = {"tarih": time.strftime("%Y-%m-%d %H:%M"), "kazanan": kazanan, "puan": puan, "sure": int(sure)}
        skorlar = []
        if os.path.exists(self.scores_file):
            try:
                with open(self.scores_file, "r", encoding="utf-8") as f: skorlar = json.load(f)
            except: pass
        skorlar.append(yeni)
        with open(self.scores_file, "w", encoding="utf-8") as f: json.dump(skorlar, f, ensure_ascii=False, indent=4)

    def show_scores(self):
        if not os.path.exists(self.scores_file):
            QMessageBox.information(self, "Skorlar", "Henüz kaydedilmiş bir oyun yok.")
            return
            
        try:
            with open(self.scores_file, "r", encoding="utf-8") as f:
                skorlar = json.load(f)
        except:
            QMessageBox.warning(self, "Hata", "Skor dosyası okunamadı.")
            return
            
        # Değişken tanımlamalarını string dışına çıkarıyoruz. 
        # Bunlar json dosyasına yazdırılacak içeriğin detayları.
        baslik = f"{'Tarih':<18} | {'Galip':<8} | {'Puan':<5} | {'Süre':<6}\n"
        icerik = ""
        
        for s in reversed(skorlar):
            dakika = s['sure'] // 60
            saniye = s['sure'] % 60
            icerik += f"{s['tarih']:<18} | {s['kazanan']:<8} | {s['puan']:^5} | {dakika:02d}:{saniye:02d}\n"

        # Kaydırılabilir metin alanı oluşturma
        from PyQt5.QtWidgets import QTextEdit
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setPlainText(baslik + "-"*45 + "\n" + icerik)
        text_edit.setFixedSize(400, 300)
        text_edit.setFont(QFont("Monospace", 9))
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Skor Geçmişi")
        msg.layout().addWidget(text_edit, 1, 0, 1, msg.layout().columnCount())
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()

    def flip_board(self):
        if self.game_started:
            return # Oyun başladıysa çevirme

        self.is_flipped = not self.is_flipped
        
        # Pulları temizle ve yeniden diz
        for p in self.pullar:
            p.deleteLater()
        self.pullar = []
        self.board_state = {i: [] for i in range(24)}
        self.kirik_pullar = {"Acik": [], "Koyu": []}
        
        self.setup_visual_board()
        # AI Motorunu tahta düzenine göre güncelle
        if self.is_flipped:
            self.ai_player = TavlaAIFlipped("Koyu")
        else:
            self.ai_player = TavlaAI("Koyu")
        
        QMessageBox.information(self, "Bilgi", "Tahta düzeni tercihinize göre değiştirildi.")
        
    def update_pul_visual_pos(self, pul, hane_id, index):
        if hane_id == -1: # Bar/Kırık pul durumu
            target_x = self.bar_x
            target_y = self.bar_y_top if pul.renk == "Koyu" else self.bar_y_bottom
        else:
            is_top = hane_id <= 11
            # Hane indeksine göre x ve y listelerini seç
            x_idx = 11 - hane_id if is_top else hane_id - 12
            target_x = self.x_points[x_idx]
            y_list = self.y_top_points if is_top else self.y_bottom_points
            target_y = y_list[min(index, 4)]

        if self.is_flipped:
            # Board_area genişliğin 533, yüksekliğin 468. 
            # Pulları bu sınırlara göre 180 derece simetriğine taşıyoruz:
            final_x = 533 - target_x
            final_y = 468 - target_y
            pul.move(final_x - 21, final_y - 21)
        else:
            pul.move(target_x - 21, target_y - 21)
        
    def show_about(self):
        """Program hakkında bilgiler içeren pencereyi gösterir."""
        about_msg = QMessageBox(self)
        about_msg.setWindowTitle("Demli Tavla Hakkında")
        
        # Program ikonunu pencerede gösterir (64x64 boyutunda)
        if not self.windowIcon().isNull():
            about_msg.setIconPixmap(self.windowIcon().pixmap(64, 64))
        
        # HTML formatında içerik
        text = (
            f"<h2 style='margin-bottom: 0;'>Demli Tavla Hakkında</h2>"
            f"<hr>"
            f"<b>Sürüm:</b> 1.0.0<br>"
            f"<b>Lisans:</b> GNU GPLv3<br>"
            f"<b>UI:</b> Python PyQt5<br>"
            f"<b>Geliştirici:</b> A. Serhat KILIÇOĞLU (shampuan)<br>"
            f"<b>Github:</b> <a href='https://www.github.com/shampuan'>www.github.com/shampuan</a><br><br>"
            f"Demli Tavla; geleneksel tavla keyfini, bir Türk Kafe'sindeymişsiniz gibi yaşatmayı amaç edinen, açık kaynaklı bir masa oyunudur.<br><br>"
            f"Bu program hiçbir garanti getirmez.<br><br>"
            f"Telif Hakkı © 2026 - A. Serhat KILIÇOĞLU"
        )
        
        about_msg.setTextFormat(Qt.RichText)
        about_msg.setText(text)
        
        # Tamam butonu
        about_msg.setStandardButtons(QMessageBox.Ok)
        about_msg.button(QMessageBox.Ok).setText("Tamam")
        
        about_msg.exec_()
        
    def run_ai_turn(self):
        """AI için zar atma işlemini başlatır."""
        if self.turn == "Koyu" and not self.dice_rolled and not self.is_paused:
            self.roll_dice_anim()

    def execute_ai_move(self):
        if self.is_paused or self.turn != "Koyu":
            return
        
        # AI motoru kontrolü (Sadece self.ai_player kullanıyoruz)
        if not hasattr(self, 'ai_player') or self.ai_player is None:
            self.end_turn()
            return

        # AI'dan hamle al
        move = self.ai_player.hamle_sec(self.board_state, self.available_moves, self.kirik_pullar, self.pullar)
        
        if move:
            source_hane = move.get("kaynak")
            target_hane = move.get("hedef")
            move_type = move.get("tip")
            zar_used = move.get("zar")

            # 1. Pulu Bul
            pul = None
            if move_type == "kirik_giris":
                if self.kirik_pullar["Koyu"]:
                    pul = self.kirik_pullar["Koyu"].pop()
            else:
                if source_hane is not None and self.board_state[source_hane]:
                    pul = self.board_state[source_hane].pop()
            
            if not pul:
                # Korumalı çıkış
                if self.available_moves: self.available_moves.pop(0)
                QTimer.singleShot(100, self.execute_ai_move)
                return

            # 2. Zarı Düş
            if zar_used in self.available_moves:
                self.available_moves.remove(zar_used)
            

            # 3. Mantıksal Uygulama
            if move_type == "toplama":
                pul.hide()
                if pul in self.pullar: self.pullar.remove(pul)
            else:
                # Kırma kontrolü
                if self.board_state[target_hane] and self.board_state[target_hane][0].renk == "Acik":
                    kirilan = self.board_state[target_hane].pop()
                    self.kirik_pullar["Acik"].append(kirilan)
                    kirilan.move(self.bar_x - 21, self.bar_y_bottom - 21)
                    kirilan.current_hane = -1

                self.board_state[target_hane].append(pul)
                pul.current_hane = target_hane

                # 4. Görsel Hareket (is_flipped uyumlu)
            if move_type == "toplama":
                # Eğer taş toplanıyorsa, onu tahtanın dışına gönder (ekrandan çıkar)
                pul.hide()
                pul.current_hane = -2 # Toplanmış pul için özel bir ID
            else:
                # Normal hareket veya kırık girişi ise görsel konum hesapla
                if self.is_flipped:
                    # Ters düzende: 0-11 üstte, 12-23 alttadır
                    is_top_visual = target_hane <= 11
                    x_idx = target_hane if is_top_visual else 23 - target_hane
                else:
                    # Standart düzende: 0-11 üstte, 12-23 alttadır
                    is_top_visual = target_hane <= 11
                    x_idx = 11 - target_hane if is_top_visual else target_hane - 12
                
                target_x = self.x_points[x_idx]
                y_list = self.y_top_points if is_top_visual else self.y_bottom_points
                h_cnt = len(self.board_state[target_hane]) - 1
                target_y = y_list[min(h_cnt, 4)]
                
                pul.move(target_x - 21, target_y - 21)
                pul.show()

            self.update_moves_display()
            self.check_win_condition("Koyu")
            
            if self.available_moves and self.check_any_legal_move():
                QTimer.singleShot(800, self.execute_ai_move)
            else:
                QTimer.singleShot(500, self.end_turn)
        else:
            self.end_turn()

if __name__ == "__main__":
    app = QApplication(sys.argv); app.setFont(QFont("Liberation Sans"))
    window = DemliTavla(); window.show(); sys.exit(app.exec_())
