# Fil Vakası: Shorts/Reels/TikTok videosu

**Çıktı:** `fil-vakasi.mp4` (1080×1920 dikey, 30 fps, H.264 + AAC, ~71 sn, -14 LUFS) ve `fil-vakasi.srt`

Dağlar ve nehirler videolarıyla aynı üretim hattını kullanır (three.js + Playwright + ffmpeg + Google TTS). Bu kez geri sayım yerine 7 bölümlük bir anlatı var.

## İçerik yaklaşımı
- Dini hassasiyet nedeniyle **hiçbir insan figürü gösterilmez**. Hikâye çöl vadisi, Kâbe, fil, ordunun meşaleleri ve mızrakları, deve sürüsü ve ebabil kuşlarıyla anlatılır.
- Mucizevi kısımlar (filin çökmesi, kuşlar) ekranda **"Rivayete göre"** etiketiyle gösterilir. Giriş ekranında "İslami kaynaklara ve rivayetlere göre" notu yer alır.
- Tarih "MS 570 civarı" olarak verilir; kaynaklar arasında farklı tarihler vardır.

## Sahneler
1. **Giriş:** Gece, Kâbe ve ordu kampı görünür.
2. **Yemen haritası:** San'a'dan Mekke'ye uzanan rota çizilir.
3. **Ordunun yürüyüşü:** Fil yürür; meşaleler, sancaklar ve toz bulutu görünür.
4. **Develer:** Ekranda 200 deve sayacı yer alır.
5. **Abdülmuttalib'in sözü:** Söz, Kâbe önünde bir alıntı kartıyla gösterilir.
6. **Filin çökmesi:** Fil Kâbe'ye doğru çöker.
7. **Ebabil kuşları:** Kuş sürüsü gelir, taşlar düşer ve meşaleler tek tek söner.
8. **Fil Suresi:** Surenin Türkçe meali gösterilir.
9. **Özet ve çağrı:** Olayın kısa özeti ve "Yorumlara yaz" çağrısı.

## Ses tasarımı
- Müzik: Hicaz makamında drone, ney benzeri melodi ve def/darbuka ritimleri.
- Efektler: Sentezlenmiş fil boru sesi, ordunun ayak sesleri, kanat çırpışları, taş ıslıkları ve rüzgâr.
- Seslendirme sırasında müzik ve efektler otomatik olarak kısılır (ducking).

## Yeniden üretmek
```bash
python3 gen_vo.py
cd build && ln -s ../../viral-video-dag/build/node_modules node_modules
node render.js video && python3 sound.py
ffmpeg -i video_noaudio.mp4 -i mix.wav -c:v copy -c:a aac -b:a 192k -shortest ../fil-vakasi.mp4
```
