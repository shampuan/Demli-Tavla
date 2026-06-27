# tavla_ai_flipped.py
import random

class TavlaAIFlipped:
    def __init__(self, renk="Koyu"):
        self.renk = renk

    def hamle_sec(self, board_state, available_moves, kirik_pullar, pullar):
        all_legal_moves = self.get_all_legal_moves(board_state, available_moves, kirik_pullar, pullar)
        if not all_legal_moves:
            return None

        # 1. Kırık girme önceliği
        kirik_girisler = [m for m in all_legal_moves if m["tip"] == "kirik_giris"]
        if kirik_girisler:
            return random.choice(kirik_girisler)

        # 2. Taş toplama önceliği
        toplama_hamleleri = [m for m in all_legal_moves if m["tip"] == "toplama"]
        if toplama_hamleleri:
            return max(toplama_hamleleri, key=lambda x: x["zar"])

        # 3. Stratejik seçim
        stratejik = [m for m in all_legal_moves if m.get("vurdu_mu") or m.get("kapi_yapti_mu")]
        if stratejik:
            return random.choice(stratejik)

        # Ev dışındaki taşları (hane >= 6) ilerletmeyi önceliklendir
        ev_disi_hamleleri = [m for m in all_legal_moves if m["tip"] == "normal" and m.get("kaynak", -1) >= 6]
        if ev_disi_hamleleri:
            return random.choice(ev_disi_hamleleri)

        return random.choice(all_legal_moves)

    def get_all_legal_moves(self, board_state, available_moves, kirik_pullar, pullar):
        legal_list = []
        if not available_moves:
            return legal_list
            
        possible_zars = sorted(list(set(available_moves)), reverse=True)
        
        # 1. KIRIK GİRİŞ (Flipped AI için giriş haneleri: 18, 19, 20, 21, 22, 23)
        # Eğer + yönde hata alıyorsak, giriş yerini 23-z+1 (yani 18-23 arası) yapıyoruz.
        if kirik_pullar[self.renk]:
            for z in possible_zars:
                target = 24 - z
                if self.is_legal(board_state, target):
                    legal_list.append({"tip": "kirik_giris", "zar": z, "hedef": target})
            return legal_list

        # 2. TAŞ TOPLAMA (Flipped AI için toplama alanı: 0, 1, 2, 3, 4, 5)
        # Eğer AI ters yöne gidiyorsa, evi burasıdır.
        can_bear_off = all(h_id <= 5 for h_id, p_list in board_state.items() 
                          if p_list and p_list[0].renk == self.renk)
        
        if can_bear_off:
            for z in possible_zars:
                target_h = z - 1
                if target_h in board_state and board_state[target_h] and board_state[target_h][0].renk == self.renk:
                    legal_list.append({"tip": "toplama", "zar": z, "kaynak": target_h})
                else:
                    present_haneler = [h for h, p in board_state.items() if p and p[0].renk == self.renk]
                    if present_haneler:
                        max_h = max(present_haneler)
                        if (max_h + 1) < z:
                            legal_list.append({"tip": "toplama", "zar": z, "kaynak": max_h})

        # 3. NORMAL HAMLE (Azalarak hareket: 23 -> 0)
        for h_id, p_list in board_state.items():
            if p_list and p_list[0].renk == self.renk:
                for z in possible_zars:
                    target = h_id - z
                    if target >= 0 and self.is_legal(board_state, target):
                        move_data = {"tip": "normal", "kaynak": h_id, "zar": z, "hedef": target}
                        
                        target_content = board_state[target]
                        if len(target_content) >= 1 and target_content[0].renk != self.renk:
                            move_data["vurdu_mu"] = True
                        if 1 <= len(target_content) < 2 and target_content[0].renk == self.renk:
                            move_data["kapi_yapti_mu"] = True
                            
                        legal_list.append(move_data)
        
        return legal_list

    def is_legal(self, board_state, target):
        if target < 0 or target > 23:
            return False
        target_content = board_state[target]
        if len(target_content) >= 2 and target_content[0].renk != self.renk:
            return False
        return True
