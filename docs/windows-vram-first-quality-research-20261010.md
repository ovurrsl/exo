# Windows: VRAM önceliği, RAM taşması ve cevap doğruluğu araştırması

Araştırma başlangıcı: 10 Ekim 2026, 20:53 UTC. Konu dalı:
`work/windows-vram-first-quality`. Üretim kodu değiştirilmeden kaynak, önceki
kabul kayıtları, kullanıcının ekran görüntüleri ve mevcut EXO günlükleri incelendi.

## Sonuç ve önceki kabulün sınırı

Mevcut deneysel yol büyük modeli yükleyip üretim yapabiliyor, ancak **VRAM'de
kalıcı ağırlık tutup yalnız taşan kısmı RAM'e bırakmıyor**. Bütün bileşenlerin
CPU kopyalarını tutuyor; bir decoder katmanını GPU'ya taşıyor, çalıştırıyor,
tamamlanmasını bekliyor ve tekrar host ağırlıklarına dönüyor. Embedding, son norm
ve çıkış head'i CPU'da. Kullanıcının VRAM önceliği isteği bu yolda tamamlanmış değil.

Önceki 32B kabulü kısa, sabit İngilizce istemlerde sıcaklık 0 kullanıyordu.
Yükleme, sınırlı üretim, uzun girdiyi işleme, iptal/toparlanma ve düzgün kapanışı
doğruladı. Normal sıcaklık/top-p/top-k ile çok dilli sohbet doğruluğunu doğrulamadı.
Kullanıcının `naber?` karşılığında sayı dizisi aldığı bildirimi ayrı doğruluk
regresyonu olarak ele alınmalıdır; yavaşlık bunu tek başına açıklamaz.

## Ölçüm ve kaynak kanıtları

| Kanıt | Bulgular | Sınır |
|---|---|---|
| Kullanıcının GPU ekranı | Ayrılmış 1,4/12 GB, paylaşılan 18,0 GB; arayüz yaklaşık 0,1 token/s | Tüm GPU süreçlerinin toplamı; yalnız EXO'ya ait ölçüm değil |
| Kullanıcının RAM ekranı | 38,2/47,3 GB kullanım, 9,1 GB kullanılabilir | Aynı anda çalışan diğer uygulamaları da içerir |
| Yerel safetensors başlıkları | 18.429.667.328 bayt toplam; 64 decoder, her biri 274.289.152 bayt; embedding ve untied head ayrı ayrı 437.575.680 bayt | Mantıksal tensor boyutu; workspace/KV/transfer geçicileri dahil değil |
| `windows_text_offload.py` | Tüm bileşenleri CPU'da canonicalize eder; `stage()` sonunda synchronize/host restore/cache clear; resident katman planı yok | Kaynak incelemesi, yeni performans benchmark'ı değil |
| MLX CUDA `allocator.cpp` | Windows'ta concurrent managed memory yoksa CPU tahsisi `cudaMallocHost`; GPU stream tahsisi `cudaMallocAsync`/`cudaMalloc` | Ekrandaki tüm shared kullanımının süreç bazında kesin atfı yapılmadı |
| Canlı EXO günlüğü | İlk hatalı istek sıcaklık 0,7/top-p 0,95/top-k 20; ikinci 0,7/0,8/20 ve thinking kapalı | İlk istek de hatalı; prefix cache tek başına neden sayılamaz |
| Cache günlüğü | `use_prefix_cache=False` görünen ikinci istekte 51/75 token cache hit | Kaynak bu flag'i yalnız bench koşulunda kapatıyor; sözleşmesi ayrıca test edilmeli |
| Model silindikten sonraki okuma | Instance listesi boş; NVML GPU kullanımı yaklaşık 1,45 GB, host kullanılabilir yaklaşık 30,25 GB | Tek temiz kapanış gözlemi; genel sızıntı yokluğu kanıtı değil |
| PCIe okuması | Mevcut ilan edilen sınır Gen4 ×16; önceki donanım raporunda GPU Gen5, host sınırı Gen4 | BIOS/riser fiziksel durumu değiştirilmedi; VRAM kapasitesini artırmaz |

Kaynaklar: `src/exo/worker/engines/mlx/windows_text_offload.py`,
`src/exo/worker/engines/mlx/utils_mlx.py`,
`src/exo/worker/engines/mlx/generator/generate.py` ve yerel
`mlx-src-0323/mlx/backend/cuda/allocator.cpp`.

Paylaşılan GPU belleği sistem RAM'idir; ayrılmış VRAM ile aynı hızda ikinci VRAM
havuzu sayılmaz. Microsoft bunu [Task Manager bellek açıklamasında](https://devblogs.microsoft.com/directx/gpus-in-the-task-manager/)
ayırıyor. NVIDIA [aktarım rehberinde](https://docs.nvidia.com/cuda/cuda-c-best-practices-guide/index.html#data-transfer-between-host-and-device)
host/device aktarımını azaltmayı, küçük aktarımları birleştirmeyi ve aşırı pinned
host bellekten kaçınmayı öneriyor. Sürücünün otomatik
[sysmem fallback özelliği](https://nvidia.custhelp.com/app/answers/detail/a_id/5490)
ayrı bir mekanizma; ekran tek başına onun devreye girdiğini kanıtlamıyor.

## Kullanıcının istekleriyle karşılaştırma

| İstek | Mevcut durum | Yapılacak / kabul sınırı |
|---|---|---|
| Önce VRAM, yalnız taşan ağırlıklar RAM | Tam sığan model normal GPU yolunda; büyük modelde tüm katmanlar taşınıyor | Resident ağırlık planı ve overflow-only host sahipliği gerekli |
| 12 GB'dan büyük model tek PC'de | Pinned Qwen3-32B ile yükleme/greedy üretim kanıtı var | Normal sampling ve Türkçe/multi-turn doğruluğu açık |
| Token hızı, verimlilik | Yaklaşık 0,11 token/s; CPU head ve tekrarlanan staging var | Süreleri ayrı ölç; GPU head, resident decoder ve sınırlı transfer uygulanmalı |
| Yeşil/sarı/kırmızı model listesi | VRAM / RAM offload / unavailable ayrımı var; MoE yanlış sarı işareti düzeltildi | Yeni gerçek bellek planıyla loader/admission/UI eşliği tekrar doğrulanmalı |
| Mac kaynakları, palet ve düzen | Bu konu Windows CUDA'ya özgü; Swift/pin/ortak şema korunmalı | Mac-only ve normal CUDA regresyonu zorunlu |
| Varsayılan port | 52415 korunuyor | Tanılama portları ürün varsayılanını değiştirmeyecek |
| Cache, kapasite ve NVML | NVML host RAM'e düşmüyor; cache sınırı/eviction düzeltmeleri var | Gerçek peak, KV büyümesi, cache flag ve başka uygulamanın VRAM tüketmesi test edilecek |
| Güvenlik ve kalite | Strict built-in loader, remote Python reddi; scoped inceleme var | Tam repo güvenlik onayı yok; doğruluk için örnek kısa yanıt yeterli değil |
| Ayrı dallar ve adım adım commit | Yeni araştırma ayrı konuda | Düzeltmeler ayrı commit; yalnız doğrulanmış kaynak windows-native'a birleşecek |
| Windows masaüstü/paket | 417be runtime ve imzasız review installer var | Yeni kaynak yeniden frozen test edilmeli; temiz kurulum/imza/yayın bekliyor |
| Claude/upstream/ex-exo/iOS dalları | Sabit tarihteki inceleme raporları mevcut | Yararlı değişiklikler seçilerek alınmalı; araştırma otomatik toplu merge izni değildir |
| Altı upstream PR | Önceki review raporu var | Yeni bellek konusu bu PR'ların tamamını çözmüş sayılmaz |
| Mac kümelemesi, Thunderbolt | Kullanıcı sonradan planda bırakılmasını istedi | Bu araştırma fiziksel küme/Thunderbolt kabulü iddia etmiyor |
| PCIe Gen5 ×16 | GPU destekliyor; sistem sınırı Gen4 görünüyor | Önceki BIOS/donanım raporu geçerli; yazılım optimizasyonundan ayrı fiziksel kabul |
| Vision/image/tensor parallelism | Önceki ayrı kayıtların kapsamı var | RAM offload bunları destekliyor diye ilan edilmeyecek |

Önceki kayıtlar: [model kapasitesi](windows-model-capacity-20261010.md),
[Claude tabanı](windows-claude-baseline-review.md),
[upstream seçili entegrasyon](upstream-integration-20261010.md),
[eski ex-exo](ex-exo-branches-20261010.md),
[PR incelemesi](upstream-pr-review-20261010.md),
[BIOS/PCIe](windows-bios-pcie-20261010.md).
Bu rapor remote dalların bugünkü tüm head'lerinin yeni bir taraması değildir.

## Öncelik ve araştırma kapıları

1. **P0 cevap doğruluğu:** gerçek 151.936 sözlükte CPU/GPU sampling support
   invariants; top-p, top-k ve categorical ayrı testler. Gerekirse gerçek BF16
   head ve decoder logits/KV karşılaştırmaları. Türkçe yeni sohbet, çok turlu
   sohbet, thinking açık/kapalı, sıcaklık 0 ve modelin önerdiği sampling ayarları.
2. **P1 VRAM residency:** gerçek boş VRAM'den KV/workspace/transfer rezervlerini
   ayır; önce GPU output head/norm, ardından kalıcı decoder katmanları. Yalnız
   overflow bileşenleri host'ta tut; resident bileşenlerin kalıcı CPU kopyasını
   kaldır. Yükleme başarısızlığında sahip olunan GPU referanslarını temizle ve
   kontrollü hata ver; sessiz sürücü/CPU fallback başarısı ilan etme.
3. **P1 ölçüm:** GPU hesaplama, transfer, CPU head, prefill, decode, TTFT,
   dedicated/global shared/RSS/host available ayrı raporlanmalı. Bütün host model
   baytlarını GPU kapasitesine eklemek veya düşük GPU %'sini tek başına arıza
   saymak yanlış olur.
4. **Kabul:** yeni kaynakta gerçek büyük model, normal sampling, cache, iptal,
   restart, baskı altında VRAM; sonra frozen runtime/desktop/installer. Hız kazancı
   ölçülmeden sayı veya genel mimari desteği vaat edilmez.

## Tamamlanan sayısal tanılama

151.936 sözlük boyutunda FP32/BF16 CPU ve CUDA sampling karşılaştırması geçti:
top-p/min-p/top-k destek kümeleri ve 12 seed'li örnek eşleşti. Bu sonuç yalnız
sampler'ı kapsar; gerçek model logits'lerinin doğru olduğunu kanıtlamaz.

Gerçek, sabit revision'daki 151.936 × 5.120 quantized output head ile sabit
BF16 girdilerde **CPU hesaplama sapması doğrulandı**. Girdi büyüklüğü 1 olan
tek satırda CPU argmax 28245, CUDA argmax 81874; en büyük mutlak fark 1,15625.
0,1 ve 5 büyüklüklerinde de argmax farklı. İki satırlı durumda argmax eşleşse
de top-20 ve logits farklı. Bütün çıktılar finite olduğu için yalnız NaN kontrolü
bu hatayı yakalayamaz.

Windows scalar CPU quantized matmul yolu BF16 toplamı her adımda tekrar BF16'ya
yuvarlıyor. Yalnız işlem girdisi/scales/biases FP32'ye çevrildiğinde packed U32
ağırlıklar değiştirilmeden argmax CUDA ile eşleşti; seçili satırlarda bağımsız
FP32 dequantize/matmul referansından en büyük fark 0,000007153 oldu. Ölçülen
tek head satırı BF16 CPU'da 4,80 s, FP32 CPU'da 0,350 s, CUDA'da 0,0159 s.
Bu süreler bütün modelin token hızını temsil etmez.

Ham kayıtlar worktree'nin ignored `build/acceptance/windows-sampling-quality-diagnostic-20261010/`
altında `head-comparison.json`, `sampler-cpu.json`, `sampler-gpu.json` olarak
tutuluyor. Tanılama rastgele sabit hidden girdileri kullanır; kullanıcının
konuşmasındaki gerçek hidden state yeniden oynatılmadı. Dolayısıyla sayısal
hata kanıtlandı, ancak sayı dizisinin tek nedeni olduğu veya sohbet kalitesinin
düzeldiği henüz iddia edilmiyor. İlk düzeltme Windows offload çıkış hesabını
FP32 birikime alacak; normal sampled Türkçe sohbet ayrı kabul kapısı olacak.

Araştırma tamamlandıktan sonra uygulama ayrı, test edilmiş commitlerle ilerler:
[uygulama planı](superpowers/plans/2026-10-11-windows-vram-first-quality.md).
