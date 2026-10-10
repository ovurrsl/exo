# Windows–Mac LAN kabulü — 10 Ekim 2026

Kullanıcının Thunderbolt olmadan devam etme kararıyla, RTX 5070 Windows PC ve bir M1 MacBook Air A2337 mevcut yerel ağ üzerinde sınandı. **TCP ring, iki master düzeninde pipeline üretimi, Windows düğümü durdurma, aktif üretimi iptal ettikten sonra toparlanma ve benchmark API'sinde prefix cache geçti.** Bu sonuç tek Mac ve küçük Qwen modeli içindir; bütün planın veya kararlı sürümün tamamlandığı anlamına gelmez.

## Kaynak ve runtime kimliği

- Windows frozen runtime **`7d11c690b321169fde843d90bc1884780731cd1a`** checkout'ından, temiz PyInstaller analysis ile yeniden üretildi. Model/chat Dashboard kaynakları bu batch'te değişmediğinden mevcut Dashboard build'i kullanıldı.
- Windows MLX: **`0.32.3.dev20261009+win.3`**. Wheel SHA-256: `045831dade422768798c314e63d4a8324873d8b3f64c12097ba4a6d3841885b2`. MLX import/kernel, spawned runner, compilerless CPU/CUDA ve ring/fault dahil **32 runtime kapısı geçti**.
- Büyük dosya kapısı atlanmadı: **3.093.767.283 byte**, **1.219 tensor** içeren gerçek Qwen3-VL safetensors dosyası frozen runtime'da yüklendi. Bu kapı vision sohbeti veya vision küme üretimi kabulü değildir.
- Mac izole checkout'ının Git tabanı kullanıcının istediği **`21a54c5ea0230a3bec1e1a786d200126c7e34ec6`** olarak kaldı. Ortak Python kaynakları Windows runtime girdileriyle **278 dosyada** hash doğrulanarak eşitlendi; önceki içerik yedeklendi. Fiziksel model harness'i üretim Python kaynaklarını ve aynı model snapshot'ını iki düğümde tekrar doğruladı.
- Mac MLX: **`0.32.0.dev20261010+cc3f3e60`**, kaynak commit'i `cc3f3e60be1289506125f2fa19b73b05aa770df8`. Mac native MLX yeniden değiştirilmedi. `app/EXO` Swift kaynaklarının baseline ile eşliği test sonrasında da doğrulandı.
- Fiziksel testten sonra alınan `c548f31b` yalnız Windows test fixture'ına platform mock'u ekler; `07c7e2b5` yalnız Windows Cargo TOML biçimini düzeltir. Bu commitler üretim Python/MLX davranışını değiştirmez. Native masaüstü kurucu paketinin bu kaynaklara güncellenmesi ayrı iştir.

## Gerçek ağ ve portlar

Windows rotası **Ethernet / 192.168.1.101**, Mac rotası **en0 / 192.168.1.105** olarak kaydedildi. Mac mevcut Wi-Fi/LAN yolunu kullandı; bu çalışma Thunderbolt/USB4NET veya RDMA kabulü değildir. BIOS, PCIe ve firewall ayarları değiştirilmedi.

Ürün API varsayılanı **52415** kaldı. Kabul süreçleri, kullanıcının çalışan uygulamalarından ayrılmak için ayrı namespace ve geçici API portları **43520, 43620, 43720** kullandı. Bunlar ürünün varsayılan port değişikliği değildir.

## Donanım sonuçları

| Deney                               | Sonuç | Doğrulanan kapsam                                                                                                                                                                                          |
| ----------------------------------- | ----- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Fiziksel ring, Mac rank 0 ve rank 1 | Geçti | FP32/FP16/BF16/int32; 4.096 ve 2.097.153 eleman; all_sum/all_gather ve komşu aktarımı. Her iki rank sırası geçti, timeout olmadı.                                                                          |
| Windows master, Qwen3-0.6B-4bit     | Geçti | Model gerçekten iki düğüme Pipeline/MlxRing ile bölündü; üç sabit sohbet, instance silme, iki worker ve iki node normal çıkış 0.                                                                           |
| Mac master, aynı model              | Geçti | Mac'in master oluşu loglardan doğrulandı; üç sabit sohbet, instance/worker temizliği, normal çıkış 0.                                                                                                      |
| Windows node stop                   | Geçti | Üç sohbetten sonra yalnız sahip olunan Windows node named Event ile kapandı; Mac'teki instance ve runner'lar da boşaldı. Zorla temizleme gerekmedi.                                                        |
| Aktif SSE client disconnect         | Geçti | İlk içerik geldikten sonra bağlantı kapandı; iki rank toparlandı, aynı instance yeni “hello” sohbetini üretti. İptal ve sonraki üretim toplam 7,06 saniye.                                                 |
| Aktif `/v1/cancel`                  | Geçti | Canlı stream command'ı iptal edildi; aynı instance sonraki sohbeti üretti. İptal ve sonraki üretim toplam 6,716 saniye.                                                                                    |
| Açık prefix cache seçeneği          | Geçti | `/bench/chat/completions` üzerinde `use_prefix_cache=true`; üç üretimde `generation_stats` doğrulandı, cache sonucu sırasıyla `none`, `partial`, `partial`. Instance drain ve tüm worker/node çıkışları 0. |

Ek uzun-prompt benchmark deneyi de geçti: **2.825 token** iki kez işlendi, 128 çıktı tokenı bütçesinde yanıt kontrolleri ve `none`, `partial`, `exact` cache sonuçları doğrulandı. Instance drain ve tüm worker/node çıkışları 0 oldu. İlk 24-token çıktı bütçeli deney, yanıt erken kesildiğinden başarısız olarak ayrı dizinde korundu; kabul sayılmadı.

Başarılı deneylerde 20 tamamlanmış sohbet yanıtı ve iki kesilmiş üretim sınandı. Aynı istemde “hello”, “two plus two is four”, ardından yeniden “hello” sonuçları değerlendirildi; bit düzeyinde backend eşitliği iddia edilmedi. `use_prefix_cache` seçeneği benchmark request şemasında tanınır; normal chat request'inde bu ek alan dikkate alınmadığından, açık seçenek kabulü ayrı benchmark deneyiyle doğrulandı. CUDA grubunda ortak eviction logları da görüldü; maksimum context ve yüksek VRAM basıncı matrisi ayrıca gereklidir.

Benchmark yolu EOS tokenlarını bilinçli olarak yasaklayıp sabit çıktı uzunluğu ölçer (`generate.py` içindeki `is_bench` logits processor); `finish_reason=length` normal sohbetin EOS kabulü değildir. Normal Windows-master sohbetlerinin üçü `stop` ile sonlandı. Aynı yerel snapshot'ın ayrı tek-CUDA kontrolünde de normal EOS'lu uzun prompt ve aritmetik üretimi `stop` verdi. Bu kontrol, EOS'u yasaklayan benchmark ile aynı koşulda karşılaştırma değildir.

## Test ortamındaki düzeltmeler ve açık bulgular

Mac'te ilk pytest girişimi `exo_tools` import yolu eksik olduğundan başlayamadı. Workspace `tools/src` Python yoluna eklendi; dependency pin'leri değiştirilmedi. Ardından bir Windows CUDA testi, `sys.platform` mock'u eksik olduğu için Mac'te yanlış dalı çalıştırdı. **`c548f31b`** bu fixture'ı düzeltir: Mac **687 geçti, 14 atlandı, 190 slow dışlandı**; Windows **728 geçti, 8 atlandı, 190 slow dışlandı**. Atlanan testler donanım kabulü sayılmaz. Windows'a özgü script/Rust test kapsamı Mac'in izole paketinde aynı değildir; sayılar birebir karşılaştırılmamalı.

İlk explicit-cancel denemesinde test istemcisi geçici SSE iterator'unu erken kapattı; API'nin aktif command kuyruğu kapandığından 404 alındı. Bu koşulda Mac worker cleanup normal çıkış şartını da sağlamadı. İlk deney başarısız olarak korundu. Iterator referansı canlı tutulup **yeni çıktı dizininde** tekrarlandığında her iki iptal/toparlanma, instance drain ve tüm worker çıkış 0 şartları geçti. Başarısız kayıt kabul kanıtı olarak kullanılmaz.

Başarılı tekrarın cleanup logunda, instance zaten silindikten sonra ulaşan ikinci `DeleteInstance` komutu için `Instance ... not found` uyarısı görüldü. Command processor çalışmaya devam etti ve drain/çıkış kapıları geçti; retry/idempotence kaynaklı bu gürültü takip işi olarak açık tutulur. Bu test aktif peer kablosunu kesme, uzun-context kill veya bütün stalled-peer matrisini kapatmaz.

Hosted Windows checks **[38058351187](https://github.com/ovurrsl/exo/actions/runs/38058351187)**, `7d11c690` için beş job'ın tamamında başarı verdi: Windows CPU/Rust, desktop/UI, Dashboard, Windows ve Darwin Python tip kontrolü. **[38059626301](https://github.com/ovurrsl/exo/actions/runs/38059626301)** üzerinde `07c7e2b5` için aynı beş job da geçti. Mac Nix build tamamlandı; önce Windows Cargo TOML biçimi, sonra `.typings/mlx_lm/tokenizer_utils.pyi` satır sarımı treefmt'i durdurdu. **`07c7e2b5`** Taplo biçimini, **`02b5604f`** stub biçimini düzeltir. TOML ve Python AST semantik eşliği, formatter idempotence ve 285 stub biçimi doğrulandı. Son düzeltmede Windows 728 test, her iki platform tipi ve Ruff kontrolleri geçti. `02b5604f` üzerinde **[Darwin Nix job'ı](https://github.com/ovurrsl/exo/actions/runs/38061185950/job/114239608181)** hem build hem `nix flake check` ile başarılı tamamlandı. Aynı workflow'daki iki Linux job'ı NVSHMEM native bağımlılık hatasıyla başarısız kaldı; bütün CI yeşil değildir.

## Kanıt dosyaları ve temizleme

Yerel kanıtlar `build/acceptance/` altında tutulur ve source repository'ye model, özel SSH anahtarı, tam kişisel log veya büyük binary eklenmez:

- `upstream-integrated-runtime-build-20261010.log`, `dist/windows/runtime-gates.json`, runtime manifest;
- `mixed-ring-integrated-lan-20261010/mixed-ring.json` ve dört rank logu;
- `mixed-model-integrated-lan-{windows-master,mac-master,node-stop}-20261010/mixed-model.json`;
- `mixed-model-integrated-lan-cancel-recovery-retry-20261010/mixed-model.json`; ilk başarısız deney ayrı dizinde;
- `mixed-model-integrated-lan-prefix-cache-20261010/mixed-model.json` ve üç üretimin cache istatistikleri;
- `mixed-model-integrated-lan-long-context-retry-20261010/mixed-model.json`; ilk 24-token çıktı bütçeli başarısız deney ayrı dizinde;
- `long-context-single-cuda-reference-20261010.json`: normal EOS'lu, benchmark ile koşulları farklı tek-CUDA kontrolü;
- `mac-platform-fixture-{windows,mac}-suite-20261010.log`, `integration-review-platform-gates-20261010.md`;
- `upstream-integrated-{mac,windows}-lan-cleanup-20261010.*`.
- `mac-after-prefix-lan-cleanup-20261010.log`, `windows-after-prefix-lan-cleanup-20261010.json`.
- `windows-lan-final-owned-process-check-20261010.json`: uzun-prompt ve kurucu derlemesi sonrasında frozen test runtime yolunda sıfır süreç; salt okunur kontrol.

Test sonunda Windows frozen runtime'ına ve Mac izole Python node'una ait süreç kalmadığı doğrulandı; ayrı prefix cache deneyi sonrasında aynı süreç ve Mac uygulama kaynak kontrolleri yeniden geçti. Yalnız bu çalışmanın PID ve başlangıç zamanı doğrulanan süreli `caffeinate` yardımcısı kapatıldı. Prefix cache deneyinin uyku önleyicisi node PID'sine bağlıydı ve node çıkınca normal kapandı. Kullanıcının mevcut Mac EXO uygulaması değiştirilmedi.

Windows panel/Settings P1 düzeltmeleri **`de85b2cf`** ile tamamlandı ve **`f99234db`** ile `windows-native`'e birleştirildi. Bu birleşik commit'in **[Windows checks](https://github.com/ovurrsl/exo/actions/runs/38061981735)** workflow'unda beş job da geçti; ayrıntılı kanıt ve kalan native kabul [masaüstü raporunda](windows-desktop-acceptance-20261010.md). Sırada temiz Windows kurulum, native Settings/DPI, ikinci M1/üç cihaz, maksimum context ve gerçek bellek baskısı, production RAM offload admission, karma offload/ileri dağıtık özellikler ve çalışan güvenlik taraması var. Thunderbolt testi kullanıcı kararıyla ertelenmiş durumda.
