# Türkiye'nin En Uzun 10 Nehri: Shorts/Reels/TikTok videosu

**Çıktı:** `turkiyenin-en-uzun-10-nehri.mp4` (1080×1920 dikey, 30 fps, H.264 + AAC, ~73 sn, -14 LUFS) ve `turkiyenin-en-uzun-10-nehri.srt`

Dağlar videosuyla (`../viral-video-dag`) aynı üretim hattını kullanır. Farkları:
- **3D:** Her nehir için arazide vadi, kanyon (Fırat, Dicle, Murat), ova (Seyhan, Ceyhan) ya da menderes (Büyük Menderes, Kızılırmak) oyuldu. Su yüzeyi akan dokuyla canlandırıldı ve suyun rengi nehre göre değişiyor (Kızılırmak kızıl, Yeşilırmak yeşil, Aras bulanık). Kamera nehri akış yönünde drone gibi takip ediyor.
- **Grafik:** Ekranda km sayacı ve 0 ile 1.355 km arasını gösteren uzunluk çubuğu var. Önceki nehirler çubukta işaretleniyor ve kaynak → döküldüğü yer etiketi gösteriliyor.
- **Ses:** Rüzgâr yerine su akışı ve şırıltı ambiyansı kullanıldı; müzik bir ton yukarıda.

Fırat, Dicle ve Aras için yalnızca **Türkiye sınırları içindeki** uzunluk kullanıldı ve ekranda da öyle yazıyor.
Uzunluklar kaynağa göre değişebilir; paylaşmadan önce kontrol edilmesi önerilir.

## Yeniden üretmek
```bash
python3 gen_vo.py                      # Google TTS seslendirme + build/timeline.json
cd build && ln -s ../../viral-video-dag/build/node_modules node_modules   # veya: npm i three@0.170.0 @fontsource/montserrat@5.1.0
node render.js video && python3 sound.py
ffmpeg -i video_noaudio.mp4 -i mix.wav -c:v copy -c:a aac -b:a 192k -shortest ../turkiyenin-en-uzun-10-nehri.mp4
```
