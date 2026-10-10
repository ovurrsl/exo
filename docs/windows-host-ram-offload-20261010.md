# Windows sistem RAM'i ve CUDA katman aktarımı — 10 Ekim 2026

İlk fiziksel RTX 5070 denemesi başarılı: yerel Qwen3-0.6B-4bit ağırlıkları CPU stream'inde yüklenip RAM'de tutuldu; embedding ve son norm GPU'da bir forward boyunca, 28 transformer katmanı ise sırayla GPU'ya taşındı. Bu **ayrı, deneysel kabul aracıdır**; EXO'nun üretim yerleştirme politikası veya ilan ettiği GPU kapasitesi değiştirilmedi.

## Ölçülen sonuç

Sabit runtime: `mlx 0.32.3.dev20261009+win.3`. Süreç normal çıkış kodu 0 ile kapandı. İkinci çalıştırmanın makine tarafından okunabilir sonucu [kabul kaydındadır](acceptance/windows-host-ram-probe-20261010.json).

| Kontrol                                        |                      Sonuç |
| ---------------------------------------------- | -------------------------: |
| Toplam model parametresi                       |           335.372.288 byte |
| Canonical CPU parametreleri                    |           335.372.288 byte |
| Forward boyunca resident embedding + norm      |            87.517.184 byte |
| En büyük transformer katmanı                   |             8.851.968 byte |
| Deneyin eşzamanlı GPU ağırlık sınırı           | 134.217.728 byte (128 MiB) |
| İzlenen eşzamanlı GPU ağırlığı zirvesi         |            96.369.152 byte |
| Açılan / kapatılan aktarım kapsamı             |                  365 / 365 |
| Çıkışta aktif ağırlık kapsamı                  |                     0 byte |
| Full-GPU kontrolüne göre en büyük logits farkı |                        0.0 |
| Greedy token dizisi                            |      `[1, 374, 264, 4185]` |

FP32, FP16, BF16 ve paketli uint32 için host → CUDA aktarımı doğrulandı. Dört kısa prefill/decode çağrısı iki kez tekrarlandı; token, logits, bütün katmanların KV değerleri ve offset'leri full-GPU kontrolüyle eşleşti. Katman aktarımı açıldıktan sonra kasıtlı hata verildi; canonical parametre kimlikleri geri yüklendi, bütün kapsamlar kapandı ve aynı model yeniden yüklenmeden aynı token dizisini üretti.

Buradaki 96 MB **ağırlıklar için uygulamanın izlediği canlı çalışma setidir**. Toplam VRAM tüketimi değildir; KV cache, activations, kernel workspace, CUDA context ve sürücü kaynaklarını içermez. NVML ölçümleri bütün GPU'ya aittir; diğer uygulamalardan etkilenebilir ve süreç başına kesin zirve ölçümü olarak kullanılmaz.

## Yeniden çalıştırma

Aracı [scripts/windows/tests/check_host_ram_offload.py](../scripts/windows/tests/check_host_ram_offload.py) üzerinden, mevcut yerel snapshot ile çalıştırın:

```powershell
uv run --extra mlx-cuda13 python scripts/windows/tests/check_host_ram_offload.py 'C:\Models\mlx-community--Qwen3-0.6B-4bit' --output build/acceptance/host-ram-probe.json
```

Hugging Face indirmesi yapılmaz. Araç yalnız Qwen3-0.6B'nin 28 katmanlı, 1024 hidden-size, tied embedding, affine 4-bit/group64 düzenini kabul eder; custom model Python dosyası çalıştırmaz. Snapshot'ın ağırlık dosyaları en fazla 1 GiB olabilir. Başlangıçta dedicated VRAM ve host RAM kontrol edilir; 2,5 GiB GPU rezervi korunur. Deneme ayrı süreçte, 120 saniyelik dış timeout ile kabul edildi. Araç CLI'si kendi başına zaman aşımı uygulamaz; otomasyon aynı dış timeout'u kullanmalıdır.

Lazy `Load` işlemleri CPU stream'inde **oluşturulur ve değerlendirilir**. GPU kopyası array alias'i yerine CUDA'da `add` çıktısıyla oluşturulur. Katman çıktısı ve güncellenmiş KV state değerlendirilir; aynı CUDA stream synchronize edildikten sonra host parametreler geri yüklenir. Qwen3'ün tied `embed_tokens.as_linear` çıkış başlığı için embedding bütün forward boyunca korunur. Dış staging wrapper'ı `mx.compile` ile derlenmez; Python yaşam döngüsü her çağrıda yürür.

## Üretim desteği için kalan kapılar

Bu küçük model gerçek 12 GB VRAM'e zaten sığar. Yapay 128 MiB ağırlık sınırı katman aktarımını zorlar; **VRAM'den büyük model kabul testi değildir**. Uzun context, throughput, büyük pinned host havuzu ve gerçek karma Mac/Windows ring henüz offload altında doğrulanmadı.

Üretim entegrasyonunda host RAM ve dedicated VRAM iki ayrı bütçe olarak tutulmalıdır. Model ağırlıkları, replicated embedding/head, en büyük stage, geçici kopyalar, KV ve workspace ayrı hesaplanmalı; büyük model ancak bu plan doğrulanırsa kabul edilmelidir. NVML hatasında host RAM'i GPU kapasitesi gibi ilan etmek veya mevcut full-fit kontrolünü kaldırmak offload uygulaması değildir.

İlk production kapsamı açık Windows/local-node politikası, desteklenen model allowlist'i ve sahip olunan katman alt kümesi olmalıdır. Sonrasında prefix cache, iptal, stalled peer, GPU baskısı, iki master/rank sırası ve Mac-only regresyonları test edilmelidir. Mac Swift/Metal/JACCL yolu, mevcut ortak JSON şemaları ve varsayılan API portu 52415 bu denemede değişmedi.

## Kaynak incelemesinin sonucu

Sabit MLX CUDA kaynağı Windows CPU allocator'ında pinned host bellek, GPU allocator'ında ayrı CUDA allocation kullanıyor. Bu akış bütün modelin otomatik olarak VRAM'den RAM'e taşınacağı garantisini vermiyor. Mevcut görüntü üretimindeki component staging ile bu yeni metin katmanı denemesi ayrı kabul kapsamlarıdır.

NVIDIA, Windows'taki limited unified-memory modunda oversubscription desteğinin sınırlı olduğunu belgeler. MLX'in genel unified-memory anlatımı Apple silicon'a aittir. Bunlar Windows'ta iki bütçe ve açık aktarım gereksinimini destekler; tek başlarına herhangi bir büyük modelin çalışacağını kanıtlamaz. [NVIDIA Unified Memory](https://docs.nvidia.com/cuda/cuda-programming-guide/04-special-topics/unified-memory.html), [MLX Unified Memory](https://ml-explore.github.io/mlx/build/html/usage/unified_memory.html).
