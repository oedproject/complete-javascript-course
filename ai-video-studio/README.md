# AI Video Stüdyo

Mac'inde çalışan, **ücretsiz** ve **API anahtarı gerektirmeyen** bir AI video uygulaması.
Hikâyeni yazarsın → sahnelere bölünür → AI her sahnenin karesini çizer → kareler videoya dönüşür.

Tüm AI modelleri senin Mac'inde çalışır: ücret yok, kota yok, internete yalnızca modeller
ilk kez indirilirken ihtiyaç var.

## Kurulum (bir kere)

1. Bu klasörü Mac'ine indir (GitHub'da dalı açıp **Code → Download ZIP**, ya da `git clone`).
2. **Terminal** uygulamasını aç, klasöre gir ve kurulumu çalıştır:

   ```bash
   cd ~/Downloads/complete-javascript-course/ai-video-studio   # indirdiğin yere göre değiştir
   ./install.sh
   ```

   Kurulum, Python ve gerekli paketleri (PyTorch, Diffusers…) `.venv` klasörüne kurar.
   Sistemine başka bir şey dokunmaz. Birkaç dakika sürer.

## Çalıştırma

```bash
./start.sh
```

Tarayıcıda `http://127.0.0.1:8765` kendiliğinden açılır. Kapatmak için Terminal'de `Ctrl+C`.

## Kullanım

1. **Fikir / hikâye** kutusuna videonu yaz. Her satır (ya da her cümle) bir sahne olur.
   **Sahnelere böl**'e bas.
2. Sahnelerin istemlerini düzenle. Türkçe yazabilirsin; uygulama modele gitmeden önce
   İngilizceye çevirir. İstersen her sahneye bir **altyazı** ekle.
3. **Stil** seç (Sinematik, Anime, Gerçekçi…). Stil her sahneye eklenir, böylece video
   tutarlı görünür.
4. **Eksik kareleri üret**. Beğenmediğin kareyi **Yeniden üret** ile değiştir. Kendi
   görselini **Yükle** ile de koyabilirsin.
5. **Video** bölümünde modu seç ve **Videoyu oluştur**'a bas. Sonuç aynı sayfada oynar,
   **İndir** ile MP4 olarak kaydedilir.

### İki video modu

| Mod | Ne yapar | M2 16 GB'de süre |
|---|---|---|
| ⚡ **Hızlı** | Karelere kamera hareketi (yakınlaşma/kaydırma), geçiş, altyazı ve müzik ekler | Saniyeler |
| ✨ **AI hareket** | Her kareyi LTX-Video modeliyle gerçekten hareketlendirir (yağmur yağar, karakter döner…) | Klip başına birkaç dakika |

AI modunda **Hareket tarifi** alanına (sahne → Gelişmiş) neyin hareket edeceğini yazarsan
sonuç çok daha iyi olur: “kamera yavaşça yaklaşıyor, robot başını çeviriyor, yağmur yağıyor”.

## Modeller ve indirme boyutları

İlk kullanımda Hugging Face'ten indirilir, `~/.cache/huggingface` altında saklanır.

| Ne için | Model | Boyut |
|---|---|---|
| Kare (önerilen) | SDXL Turbo | ~7 GB |
| Kare (hafif) | SD Turbo | ~2.5 GB |
| Kare (en kaliteli, yavaş) | SDXL Base 1.0 | ~7 GB |
| Türkçe → İngilizce | Helsinki-NLP opus-mt-tr-en | ~300 MB |
| AI hareket | LTX-Video (2B) | ~25 GB |

> SDXL Turbo ve SD Turbo yalnızca **ticari olmayan** kullanım için ücretsizdir.
> Videoları satacaksan **SDXL Base** modelini seç (lisansı ticari kullanıma izin verir).

## 16 GB RAM için ipuçları

- AI hareket modu belleği zorlar. Çalışırken diğer ağır uygulamaları (Chrome sekmeleri,
  oyunlar) kapat.
- **AI klip kalitesi: Düşük** ve **Klip süresi: 2 sn** ile başla. Sorun yoksa artır.
- Uygulama aynı anda tek model tutar: kare modelinden video modeline geçerken önceki model
  bellekten atılır.

## Sorun giderme

- **“Test modu (AI yok)” yazıyor:** AI paketleri kurulmamış. `./install.sh`'yi yeniden çalıştır.
- **Kareler siyah çıkıyor:** macOS'u 14 (Sonoma) veya üstüne güncelle.
- **AI modunda bellek hatası:** kaliteyi “Düşük”e, klip süresini 2 sn'ye indir, diğer
  uygulamaları kapat.
- **Port meşgul:** `PORT=8800 ./start.sh`

## Geliştirici notları

```
app/server.py     FastAPI uç noktaları ve iş akışı (kare üret, video oluştur)
app/images.py     Metinden kare (Diffusers, Apple GPU/MPS)
app/video_ai.py   Kareden AI video (LTX-Video, iki aşamalı, 16 GB'a uygun)
app/compose.py    Kamera hareketi, geçişler, altyazı, müzik → MP4
app/translate.py  Yerel Türkçe→İngilizce çeviri
app/jobs.py       Tek işçili iş kuyruğu (ilerleme + iptal)
app/projects.py   Projeler diskte: projects/<id>/
static/           Arayüz (HTML/CSS/JS, kütüphanesiz)
```

AI kurmadan arayüzü denemek için: `./install.sh --no-ai` ve ardından `./start.sh`
(sahte renkli kareler üretir).
