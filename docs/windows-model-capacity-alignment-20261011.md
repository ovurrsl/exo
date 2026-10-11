# Windows model kapasitesi — 11 Ekim 2026

Model listesi ve yerleştirme aynı `cuda_text_memory_requirement` fonksiyonunu
kullanıyor. Önceki RAM offload hesabı yalnız üç ortalama decoder katmanını
sayıyordu. Gerçek yükleyicinin zorunlu GPU head/norm'u, head başlangıç tahsis
tepesi, padded KV cache'i, iki katmanlık KV büyüme geçicileri ve 256 MiB tahsis
payı eksikti. Bu nedenle yeterli RAM bulunan bir PC, GPU kapasitesi yetersizken
modeli sarı gösterebiliyordu.

Yeni katalog tahmini bu kalemleri içeriyor. Bildirilen GPU kapasitesinden
2,5 GiB runtime rezervi zaten düşüldüğünden ikinci kez eklenmiyor. FP32 KV ve
affine 4-bit/group32/FP32 scale-bias head üst sınırı kullanılıyor; gerçek
yükleyici kendi tensor boyutları ve güncel NVML değeriyle son kontrolü yapıyor.
Context limiti arttıkça katalogda gereken GPU kapasitesi de artıyor.

Tahmin denetlenmiş `mlx-community/Qwen3-0.6B-4bit` ve
`mlx-community/Qwen3-32B-4bit` stok ID/geometrileriyle sınırlı. Key/value head
sayısı biliniyorsa 8 olmalı. Aynı aile adı taşıyan özel modeller için ModelCard
vocabulary, head dtype, head_dim, grup boyutu veya en büyük decoder boyutunu
kanıtlamıyor; doğrulanmış metadata olmadan sarı uygunluk verilmiyor.
Bu sınırlama katalog/yerleştirme kabulüne ait; worker'ın mevcut güvenli
offload mimari/tokenizer kontrolü değiştirilmedi.

Stok geometrilerinin kaynağı:
[Qwen3-32B config](https://huggingface.co/Qwen/Qwen3-32B/raw/main/config.json),
[Qwen3-0.6B config](https://huggingface.co/Qwen/Qwen3-0.6B/raw/main/config.json).
32B ağırlık snapshot'ı için önceki fiziksel kabul:
`windows-vram-physical-acceptance-20261011.md`.

VRAM'e doğrudan sığan modellerin yolu, renk paleti, Mac kaynakları ve ortak
state/protokol şeması değişmedi. Sarı RAM desteğini, kırmızı yetersiz veya
doğrulanmamış offload kapasitesini ifade etmeye devam ediyor. Host kontrolü
tam model storage + yükleme geçicileri + rezerv hesabını koruyor; bu,
runtime'ın yalnız taşan ağırlıkları tutma hesabından daha muhafazakâr ve
bazı mümkün modelleri reddedebilir. Genel mimari/offload desteği değildir.

Regresyonlar: mandatory head/KV bütçesi; değiştirilmiş stok geometri reddi;
8 GiB kapasitede sarı, 2 GiB kapasitede kırmızı; doğrudan VRAM yolunda offload
politikasına dokunulmaması; worker tokenizer güvenlik yolunun korunması.

Kaynak doğrulaması: **902 test geçti, 8 atlandı, 195 slow test dışlandı**.
Windows/Darwin strict type check sıfır hata ve uyarı; Ruff ve 338 dosyanın
biçim kontrolü geçti. Atlanan kontroller donanım kabulü olarak sayılmadı.

## Paket ve çalışan uygulama

`bbe0490b` kaynağından üretilen frozen runtime **32 zorunlu kapıyı geçti**:
CUDA, derleyicisiz CPU/GPU, gerçek 5,36 GB safetensors dosyası, ring ve süreç
çıkışı. Runtime SHA-256:
`80328e943fb293ad34f542378b2000a85194c0bcb6cb9d303c4a0c343da2bbe7`.
11.441 dosyanın manifest kontrolü kaynak paket ve iki masaüstü kopyasında geçti.
Yeni runtime hash'ine bağlı yardımcı ve masaüstü yeniden derlendi.

Normal kullanıcı uygulaması 52415 üzerinde açıldı; dinleyici backend'in kendi
GUI'sinin alt süreci ve doğru runtime yolu/hash'i olduğu doğrulandı. Düğüm
keşfi tamamlandıktan sonra gerçek kapasite API'si 32B için `ram_offload`,
**6.585.794.560 bayt gerekli**, **8.910.364.672 bayt kullanılabilir** bildirdi.
Kullanılabilir değer canlı ölçümdür; sabit kapasite garantisi değildir.
İlk HTTP yanıtı bellek ölçümlerinden önce gelebilir; kabul kontrolü yalnız
HTTP 200 ile yetinmeyip beklenen düğüm/capability bilgisini de bekledi.
Kayıt: `build/windows-runtime/normal-gui-capacity-bbe0490b.json`.

Aktif model bulunmadığı kontrol edilerek yalnız sahip olunan GUI/backend
kapatıldı. Eski runtime ve GUI workspace içinde yedeklendi. Sohbetler, modeller,
ayarlar ve tasarım kaynakları değiştirilmedi. Bu paket için 32B sohbet QA'sı
tekrar çalıştırılmadı; önceki cevap doğruluğu/fiziksel yerleşim kabulü ayrı
rapordadır ve ilgili inference kaynakları bu değişiklikte değişmedi.
İmzalı installer, temiz tüketici sistemi ve Mac kümesi yayın kabulü değildir.
