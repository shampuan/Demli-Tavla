#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import random

class TavlaAI:
    def __init__(self, renk="Koyu"):
        self.renk = renk

    def hamle_sec(self, board_state, available_moves, kirik_pullar, pullar):
        """
        Mevcut tahta durumuna göre yapılabilecek en mantıklı hamleyi seçer.
        İnsani bir dokunuş için stratejiler arasında rassal seçim yapar.
        """
        all_legal_moves = self.get_all_legal_moves(board_state, available_moves, kirik_pullar, pullar)
        
        if not all_legal_moves:
            return None

        # 1. Kırık girme zorunluluğu (Kural gereği öncelikli)
        kirik_girisler = [m for m in all_legal_moves if m["tip"] == "kirik_giris"]
        if kirik_girisler:
            return random.choice(kirik_girisler)

        # 2. Taş toplama (Bear off) hamleleri - Oyunun bitmesi için öncelikli
        toplama_hamleleri = [m for m in all_legal_moves if m["tip"] == "toplama"]
        if toplama_hamleleri:
            # Stratejik olarak genellikle en büyük zarı kullanarak toplamak iyidir
            return max(toplama_hamleleri, key=lambda x: x["zar"])

        # 3. Stratejik Hamle Grupları
        vurma_hamleleri = [m for m in all_legal_moves if m.get("vurdu_mu", False)]
        kapi_hamleleri = [m for m in all_legal_moves if m.get("kapi_yapti_mu", False)]
        
        # Karar Mekanizması (Rassal Seçim)
        # %40 ihtimalle vurmaya, %30 ihtimalle kapı yapmaya odaklanır, 
        # kalan durumlarda veya bu hamleler yoksa rastgele bir yasal hamle yapar.
        sans = random.random()
        
        if sans < 0.4 and vurma_hamleleri:
            return random.choice(vurma_hamleleri)
        elif sans < 0.7 and kapi_hamleleri:
            return random.choice(kapi_hamleleri)
        else:
            return random.choice(all_legal_moves)

    def get_all_legal_moves(self, board_state, available_moves, kirik_pullar, pullar):
        """Tüm yasal hamleleri kategorize ederek listeler."""
        legal_list = []
        possible_zars = set(available_moves)
        ai_pullari = [p for p in pullar if p.renk == self.renk]
        
        # 1. KIRIK PUL KONTROLÜ
        if len(kirik_pullar[self.renk]) > 0:
            for z in possible_zars:
                target = 24 - z
                if self.is_legal(board_state, target):
                    legal_list.append({"tip": "kirik_giris", "zar": z, "hedef": target})
            return legal_list

        # 2. TAŞ TOPLAMA (BEAR OFF) KONTROLÜ
        # Tüm pullar 0-5 arasındaki hanelerde (evinde) mi?
        is_all_home = all(p.current_hane <= 5 for p in ai_pullari) if ai_pullari else False
        
        if is_all_home:
            # En uzaktaki pulun hanesini bul
            max_dist = max([p.current_hane + 1 for p in ai_pullari]) if ai_pullari else 0
            for z in possible_zars:
                target_idx = z - 1
                # Tam hane eşleşmesiyle toplama
                if target_idx < 6 and any(p.current_hane == target_idx for p in ai_pullari):
                    legal_list.append({"tip": "toplama", "zar": z, "kaynak": target_idx})
                # Büyük zarla en arkadaki pulu toplama
                elif z > max_dist and max_dist > 0:
                    legal_list.append({"tip": "toplama", "zar": z, "kaynak": max_dist - 1})

        # 3. NORMAL HAMLE KONTROLÜ
        for hane_id, pullar_in_hane in board_state.items():
            if pullar_in_hane and pullar_in_hane[0].renk == self.renk:
                for z in possible_zars:
                    target = hane_id - z
                    if target >= 0 and self.is_legal(board_state, target):
                        move_data = {"tip": "normal", "kaynak": hane_id, "zar": z, "hedef": target}
                        
                        # Hamle analizleri (Vurma/Kapı)
                        target_content = board_state[target]
                        if len(target_content) == 1 and target_content[0].renk != self.renk:
                            move_data["vurdu_mu"] = True
                        if len(target_content) >= 1 and target_content[0].renk == self.renk:
                            move_data["kapi_yapti_mu"] = True
                            
                        legal_list.append(move_data)
        
        return legal_list

    def is_legal(self, board_state, target):
        """Hedef hanenin yasal olup olmadığını kontrol eder."""
        if target < 0 or target > 23:
            return False
        target_content = board_state[target]
        # Rakibin kapısı (2 veya daha fazla pulu) varsa oraya girilemez
        if len(target_content) >= 2 and target_content[0].renk != self.renk:
            return False
        return True
