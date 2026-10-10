# EXO Windows ve NVIDIA ilerlemesi — 10 Ekim 2026

Güncel birleşik kaynak **`79de2150c1979663b63708c13dc6ddee5709f663`**, fork'ın
`windows-native` dalına gönderildi. Mac düzenini izleyen panel ve tanılama ZIP'inden
özel içeriği çıkaran düzeltme ayrı konu commitleriyle birleştirildi.
**Kararlı sürüm kabulü tamamlanmadı; `release_ready=false`.** Mac Swift/Metal/JACCL
kaynakları, Darwin dependency pin'leri, ortak strict şemalar ve varsayılan API
portu **52415** bu iki konuda değişmedi.

## Güncel durum

| Alan                   | Tamamlanan ve doğrulanan kapsam                                                                                                                                                                                                                                      | Sınır / sonraki iş                                                                                                                         |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| Mac görünümü           | `aec96839`: çekirdek GPU/sıcaklık/bellek/ilerleme bilgileri görünür; model durumunun önceliği, durum kapsülleri, Settings gezinmesi ve içerik yüksekliğine göre panel küçülmesi düzeltildi. Açık ve koyu temada 27'şer UI testi, 4 birim testi, 70 Rust testi geçti. | Fiziksel DPI, monitör, ekran çizimi ve production Settings açıcı kabulü açık.                                                              |
| Birleşik masaüstü      | `79de2150`: 27 Playwright (atlama yok), 4 Vitest ve derleme hedeflerinde toplam 76 Rust testi geçti; Svelte 0 hata/0 uyarı, TypeScript, strict Clippy ve Cargo fmt geçti.                                                                                            | Güncel hosted workflow sonuçları ayrı izleniyor; önceki yeşil commitler bu kaynağın CI kabulü değildir.                                    |
| Native Settings ölçümü | Tam `aec96839` kaynağında light/dark 10'ar örnek; fixed WebView2 `154.0.4258.62`, salt okunur DOM ve IPC.                                                                                                                                                            | Pencere gizli ve odaksızdı; opener, paint, fiziksel DPI veya kurulum kabulü sağlamaz. Sonraki ZIP değişikliği bu ölçümün kaynağı değildir. |
| Güvenlik               | `931e0ff4..0c5294ac` diff taraması tamamlandı: 187 değişen yol incelendi, 45 açık dışlama, 0 ertelenen; bir düşük önem/P3 CWE-200 bulgusu. `79d8b986` tanılama ZIP'inden ham logları ve generation payload'larını çıkardı.                                           | Düzeltme regresyon testleri geçti; yeni bir sealed tarama değildir. Sonraki arayüz ve değişmemiş bütün upstream API kapsam dışında.        |
| Gerçek LAN ve CUDA     | `7d11c690` runtime'ında RTX 5070 + tek M1: iki ring sırası, iki master düzeni, 20 tamamlanmış sohbet ve iki iptal/toparlanma; tek CUDA vision ve FLUX üretim/düzenleme geçti.                                                                                        | İkinci M1/üç fiziksel cihaz, karma vision/image ve yüksek VRAM/context matrisi açık.                                                       |
| Upstream PR'lar        | Altı açık PR'ın sabit head'leri gözden geçirildi; model kartı, namespace/workspace belgeleri, NIC uyumluluğu ve iki API güvenlik düzeltmesi ayrı raporda.                                                                                                            | PR 2305 DNS pinleme ve PR 2306 model yolu düzeltmeleri güncel main/frozen runtime'a henüz taşınmadı; seçili entegrasyon ve native CI açık. |
| Kurucu                 | Önceki `f99234db` GUI / `7d11c690` runtime kurucusu derlendi, kimliği kaydedildi; imzasız ve kurulmadı.                                                                                                                                                              | **`79de2150` kurucu derlemesi sürüyor.** Final artefakt kimliği ve kurulum sonucu henüz yok.                                               |

Ayrıntılar: [masaüstü kabulü](windows-desktop-acceptance-20261010.md),
[LAN kabulü](windows-lan-acceptance-20261010.md),
[tek CUDA vision/görüntü](windows-runtime-media-acceptance-20261010.md) ve
[altı PR incelemesi](upstream-pr-review-20261010.md).

## Verimlilikte açık işler

Salt okunur bağımsız inceleme, Python üretim kodunu `7d11c690` ve masaüstünü
`23a76e4a` üzerinden sabitledi. Yeni panel/ZIP konusu o incelemede yoktur.
Batch bellek dönüşümü baytları **%7,3741824 fazla** raporluyor; tam cache
eşleşmesindeki `prompt_tps` önceki isteğin tarihsel değerini taşıyor. Kısa istem
tekrarları gereksiz KV cache kopyaları biriktirebilir. Görsel önizlemelerin
CPU/GPU ağırlık taşıma maliyeti ve gizli pencerelerin durum sorguları henüz
ölçülmedi. Bu bulgular açık iş olarak tutulur; genel hızlanma oranı çıkarılmadı.
Yerel rapor:
`exo/build/acceptance/windows-efficiency-independent-review-20261010.md`.

[Küçük RAM–CUDA aktarım deneyi](windows-host-ram-offload-20261010.md) başarılıdır;
model gerçek VRAM'e zaten sığar. **VRAM'den büyük LLM için üretim offload'u
kabul edilmiş değildir.**

## Kalan kabul

- Geliştirme araçları olmayan temiz Windows'ta kurulum, GPU üretimi ve modelleri koruyan kaldırma.
- Production Settings açıcı, beş sekme/klavye, fiziksel DPI ve birden fazla monitör.
- İmzalı yayın/updater; güncel kaynakta hosted CI'nin tamamlanması. Önceki Linux Nix NVSHMEM/cuFile paketleme hataları açık.
- İkinci M1, üç düğüm, VRAM üstü LLM offload ve karma vision/image.
- Upstream API güvenlik düzeltmelerinin seçili entegrasyonu ve ilgili regresyonlar.

Thunderbolt fiziksel kabulü kullanıcının LAN ile devam etme kararıyla ertelendi;
[donanım incelemesi](claude-fork-thunderbolt-20261010.md) ve
[BIOS/PCIe raporu](windows-bios-pcie-20261010.md) tarihsel kanıtı içerir.

## Kimlik ve tarihsel ayrıntılar

- Panel konusu: [`aec96839`](https://github.com/ovurrsl/exo/commit/aec96839e6072f28c3c858e1f0938661ac8b8657).
- Tanılama gizliliği konusu: [`79d8b986`](https://github.com/ovurrsl/exo/commit/79d8b9863281335188cb3282cc89370b843ace79).
- Birleşik kaynak: [`79de2150`](https://github.com/ovurrsl/exo/commit/79de2150c1979663b63708c13dc6ddee5709f663).
- Önceki uygulama/entegrasyon ayrıntıları [entegrasyon raporunda](upstream-integration-20261010.md); eski ilerleme metninin tamamı [sabit tarihsel sürümde](https://github.com/ovurrsl/exo/blob/79de2150c1979663b63708c13dc6ddee5709f663/docs/windows-progress-20261010.md) korunur. Eski sayılar güncel kabul olarak taşınmadı.

Yerel log ve büyük artefaktlar `build/acceptance/` altında tutulur; kaynak
deposuna kişisel tam log, model veya kurucu binary'si eklenmez. Güncel test,
tarama ve kurucu kayıtlarının tam adları [masaüstü kabul belgesindedir](windows-desktop-acceptance-20261010.md).
