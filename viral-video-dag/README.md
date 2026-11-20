# Türkiye'nin En Yüksek 10 Dağı: Shorts/Reels/TikTok videosu

**Çıktı:** `turkiyenin-en-yuksek-10-dagi.mp4` (1080×1920 dikey, 30 fps, H.264 + AAC, ~69 sn, -14 LUFS)

| Dosya | Ne işe yarar |
|---|---|
| `turkiyenin-en-yuksek-10-dagi.mp4` | Altyazısı videoya gömülü, paylaşıma hazır video |
| `turkiyenin-en-yuksek-10-dagi.srt` | Ayrı altyazı dosyası (YouTube'a ayrıca yüklenebilir) |
| `script.json` | Senaryo: seslendirme metni, altyazı metni, dağ verileri |
| `build/index.html` | three.js ile 3D sahne ve motion graphics katmanı |
| `build/render.js` | Playwright ile kare kare render alır, ffmpeg'e aktarır |
| `build/sound.py` | Ses tasarımı: müzik, whoosh, impact, sayaç tıkları, riser, rüzgâr, ducking |

## Yapı
- **Görüntü:** Her dağ için prosedürel olarak üretilmiş gerçek 3D arazi kullanıldı. Volkanlar koni, Kaçkar/Aladağlar/Cilo sivri sırt yapısında. Kar çizgisi, gökyüzü shader'ı, sis, bulutlar ve kar parçacıkları sahnede yer alıyor. Kamera her sahnede dağın etrafında dönerek yaklaşıyor ve geçişlerde whip efekti var. #1 sırada kamera vinç çekimiyle yükseliyor.
- **Motion graphics:** Ekranda büyük sıra numarası, dağ adı, konum etiketi, sayarak artan rakım sayacı, 3.000 ile 5.137 m arasını gösteren rakım çubuğu, zirve işareti ve TOP 10 ilerleme çubuğu bulunuyor. Final sahnesi sıralama grafiğiyle bitiyor ve izleyiciyi yorum yazmaya çağırıyor.
- **Altyazı:** Kelime kelime vurgulanan büyük harfli altyazı, Reels arayüzünün üstünde kalan güvenli alana yerleştirildi.
- **Seslendirme:** Google TTS (gTTS, `tr`) ile üretildi. Konuşma hızı 1,28× yapıldı ve baştaki ile sondaki sessizlikler kırpıldı.
- **Ses tasarımı:** Am–F–C–G akorlarıyla 96 BPM'lik sinematik pad ve bas, davul, her geçişte whoosh, sıra numarası çıktığında impact, sayaçla senkron tıklar, #1'den önce riser ile müzik kesintisi ve rüzgâr ambiyansı. Konuşma sırasında müziğin sesi otomatik kısılıyor (ducking).

## Yeniden üretmek
```bash
pip install gtts numpy scipy
cd build && npm i
python3 ../gen_vo.py      # seslendirme + timeline.json
node render.js video      # video_noaudio.mp4
python3 sound.py          # mix.wav
ffmpeg -i video_noaudio.mp4 -i mix.wav -c:v copy -c:a aac -b:a 192k -shortest ../turkiyenin-en-yuksek-10-dagi.mp4
```
Rakımlar kaynağa göre birkaç metre farklılık gösterebilir (özellikle Tendürek ve Kaçkar). Paylaşmadan önce kontrol edilmesi önerilir.
