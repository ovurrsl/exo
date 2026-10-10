# Windows VRAM önceliği ve cevap doğruluğu — 11 Ekim 2026

## Kapsam

RTX 5070 üzerinde, pinned `mlx-community/Qwen3-32B-4bit` snapshot'ı
`bcaaf7f538adf166c1080a2befdb4f6019f66639` kullanıldı. Ağırlık toplamı
18.429.667.328 bayt. Bu rapor tek Windows düğümünü kapsar; Mac kümesi,
bütün model mimarileri veya tam 8K context kabulü değildir.

## Kanıtlanan hatalar

- Önceki CPU BF16 çıkış projeksiyonu token sıralamasını bozuyordu. FP32
  hesaplama düzeltmesi kaynak ve frozen runtime'da Türkçe doğruluk testlerini
  geçti. Ayrıntılar `windows-vram-first-quality-research-20261010.md` içinde.
- CUDA allocator'ın boyuta göre cache seçimi, GPU isteğine pinned CPU tamponu
  verebiliyor. GPU stream'i seçmek tek başına fiziksel VRAM sahipliğini kanıtlamaz.
  Kontrollü 512 MiB deneyinde eski cache ile NVML artışı 2 MiB; cache sınırı
  sıfırlandıktan ve mevcut cache temizlendikten sonra artış tam 512 MiB oldu.
- Logical ağırlık baytları driver/tahsis yükünü tamamen kapsamaz. Fiziksel
  yüklemede yaklaşık 39 MB ek fark ve 28 MB stage kapasite açığı gözlendi.
  Yalnız ilk planlamadan 256 MiB pay düşülüyor; 2,5 GiB runtime rezervi ve
  canlı stage eşiği değiştirilmedi. Bu pay ölçülen hedefe ait sınırlı önlemdir.
- Sonraki token'da CUDA driver pool'u 100 MiB geri verilebilir tampon tutuyordu.
  Yalnız kapasite yetersiz görünürse cache temizleniyor, NVML bir kez yeniden
  okunuyor ve aynı eşik yeniden uygulanıyor. Gerçek baskı veya NVML kaybı reddedilir.

## Uygulama ve kapanış

Windows offload modeli süreç içindeki allocator ayarını tekil olarak sahiplenir.
İlk resident tahsis öncesi cache kapatılıp temizlenir; model ömrü boyunca korunur.
Başlatma hatası ve açık kapanış önce işleri tamamlar, ağırlık referanslarını
bırakır ve önceki cache sınırını bir kez geri yükler. İkinci sahip reddedilir.
Runner kapanışı aktif isteği kapatır; EXO ve MLX LM generation akışlarını,
ardından model akışlarını tamamlar. Mac/normal inference yolu korunur.

Kalıcı GPU head/norm ve decoder prefix'i tutulur; yalnız taşan decoder ağırlıkları
RAM'den stage edilir. Bu yolda cross-request prefix cache geçici olarak kapalıdır.
KV kapasitesi yalnız canonical, değerlendirilen ve senkronize edilmiş GPU
cache sahiplerinden kredilendirilir. NumPy/DLPack ağırlık incelemesi tamponu
CPU'ya taşıyabildiğinden fiziksel ölçüm ağırlık export'u yapmadan gerçekleştirildi.

## Doğrulama

Kaynak `26e59556`: default suite **899 geçti, 8 atlandı, 195 slow dışlandı**.
Windows/Darwin strict type check sıfır hata/uyarı; Ruff ve 338 dosya biçim
kontrolü geçti. Atlanan GPU testleri bu sonuçta GPU kabulü olarak sayılmadı.
Bağımsız kaynak incelemesi lease, kapanış, tahsis payı ve dar retry'ı onayladı.
İki açık donanım testi de geçti: FP32 CPU referansı ile staging ve BF16
untied-head CUDA referansı ile KV/çıktı eşleşmesi. GPU testlerinin kendi
wrapper'larını kapatmaması ilk birlikte çalıştırmayı engelledi; testler gerçek
işleri tamamlayıp cache sahiplerini bırakan `finally` kapanışıyla düzeltildi.

Gerçek 32B doğrudan çalıştırmada fiziksel yerleşim, 3-token prefill, iki ayrı
tek-token decode, finite logits, KV offset/sahipliği ve kapanış geçti.
Planlanan resident ağırlık **5.100.501.504 bayt**, canonical RAM ağırlığı
**13.329.165.824 bayt**; toplam model ağırlığıyla tam eşleşiyor. 17 decoder
resident, 47 decoder overflow. Tek-token adımları yaklaşık **1,10–1,11 saniye**;
bu ölçüm sohbet arayüzünün TPS değeri veya genel hız garantisi değildir.

Ham kayıtlar ignored `build/acceptance/actual-32b-residency-cache-lease.json`
ve `cache-backing-experiment.json` içinde. Önceki
`actual-32b-residency.json` logical ileri hesaplama geçse de fiziksel yerleşimi
başarısızdı; kaydı açıkça `physical_residency_qualified=false` olarak işaretlendi.

Sohbet API kabulü aynı üretim kaynağıyla yalıtılmış namespace/portta tamamlandı:

| Girdi | Cevap / kabul sınırı |
|---|---|
| Naber? Türkçe kısa cevap ver. | Merhaba! Nasılsın? — stop |
| İki artı iki kaç eder? Yalnız sayıyı yaz. | 4 — stop |
| Elma kırmızıdır… | Kırmızı. — stop |
| Konuşmada adı Deniz; Benim adım ne? | Deniz — stop |
| 1.222 token elma bağlamı | The color of the apple is **red**. — stop |
| Streaming iptal sonrası toparlanma | Hello! — stop; düğüm/runner exit 0 |

Ekrandaki çıplak `naber ?` sayılar tekrarlamadı; Türkçe cevap verdi, fakat
parantez içindeki ifade doğal değildi. Belirsiz `nbaer` İngilizce açıklama
istedi ve 48-token sınırında kesildi. Bunlar genel dil kalitesi veya tamamlanmış
bir belirsiz-girdi cevabı için başarı garantisi değildir. Dört açık doğruluk
girdisi ve uzun bağlam cevabı semantik olarak kontrol edildi.

Sampling: temperature 0,7, top_p 0,8, top_k 20, min_p 0, seed 42, thinking
kapalı. Peak owned-process RSS **15.857.582.080 bayt**, peak **global** GPU
**7.335.436.288 bayt**, minimum host available **15.574.646.784 bayt**.
Global NVML değeri yalnız EXO sürecine atfedilmez. Kayıt:
`build/acceptance/qwen3-32b-resident-sampled-quality/inference.json`.

Paket, açık masaüstü runtime ve tam 8K context kabulü ayrıca doğrulanmalıdır.
Açık uygulama bu rapor yazılırken hâlâ eski runtime'ı kullanıyor.
