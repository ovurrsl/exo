# EXO Windows ve NVIDIA çalışma durumu

10 Ekim 2026. Aşağıdaki ana tablo önceki `abe3fdbb` kaynak/runtime snapshot'ıdır;
en yeni ayrı konu dalları, inceleme bulguları ve entegrasyon durumları
[güncel dal entegrasyon raporunda](upstream-integration-20261010.md) izlenir.
Windows çekirdeği, CUDA runtime ve masaüstü uygulaması geliştirildi. Önceki yeni
runtime 32 native kontrolü geçti; sonraki kurucu derlemesi dosya kilidi nedeniyle
başarısız oldu. Yeni installer ve native Settings kabulü tamamlanmadı.
**Tüm plan ve kararlı sürüm tamamlanmış değildir.** Varsayılan API portu **52415**.

Yeni ilerleme: API hata/iptal düzeltmeleri, runner lifecycle, cache retention,
Windows CI asset ve bağımsız Rust biçim kapısı ayrı dallardan `windows-native`e
birleştirildi. Birleşik kaynak `a36502ba` üzerinde **728 test geçti**, iki platform
strict tip kontrolü temiz. Küçük fiziksel Qwen RAM–CUDA katman aktarımı tekrar geçti;
[ölçüm raporu](windows-host-ram-offload-20261010.md) deneyin sınırlarını açıklar.
Üretim büyük-model offload'u henüz yok. Kullanıcı Thunderbolt olmadan mevcut LAN
üzerinden devam etmeyi seçti; Thunderbolt fiziksel kabulü ertelendi.
[GPU Gen5 x16 ölçümü ve BIOS/ALT_PCIE_MODE rehberi](windows-bios-pcie-20261010.md).
Thunderbolt kablo bağlantısı OS seviyesinde aktif eş/NIC oluşturmadı;
[anakart ve Claude dal incelemesi](claude-fork-thunderbolt-20261010.md) mevcut kanıtı içerir.

## Tamamlanan kaynak çalışmaları

| Alan              | Yapılan çalışma                                                                                                 | Doğrulama                                                                                                     |
| ----------------- | --------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Windows MLX       | Sabit kaynak/patch/wheel kimliği, paket içi NVIDIA DLL ve JIT kaynakları, derleyicisiz CPU yolu                 | Yeni frozen runtime'da 32 native kapı; gerçek 3.093.767.283 bayt safetensors yükleme                          |
| CUDA düğümü       | Ayrı süreçte kernel/ring/normal çıkış kontrolü, NVML kapasitesi, host RAM'e yanlış geçişin kaldırılması         | RTX 5070 kontrolleri ve birim testleri                                                                        |
| Karma küme        | Ortak cache eviction kararı, model snapshot kontrolü, ilerleme timeout'u ve Windows runner kapanışı             | Önceki frozen adayda PC + tek M1, iki master düzeni, üçer sohbet ve süreç çıkışları 0                         |
| Masaüstü          | Tauri/Svelte, tepsi, beş ayar sekmesi, Job Object, Credential Manager, tanılama, model korumalı kaldırma        | Kurulu önceki adayda çift açılış, gerçek GPU sohbeti, çökme temizliği, restart/stop, Unicode kurulum/kaldırma |
| Mac görünümü      | 340 px panel, 640×560 gruplu ayarlar, AppKit açık/koyu renkleri, orijinal siyah/sarı simge, Mac topoloji düzeni | Güncel kaynakta 13 açık + 13 koyu UI testi, 3 birim testi, tip kontrolü 0 hata/uyarı, üretim build            |
| Ayar penceresi    | Native boş pencere hatası için async WebView oluşturma ve sıralı reuse                                          | Rust 19 test geçti; yeni native tekrar bekliyor                                                               |
| Bellek hatası     | Yuvarlanmış eşit GB yerine GiB, tam bayt ve eksik miktar                                                        | 1 bayt eksik/gerçek yakın sınır/tam kapasite regresyonları; toplam 668 Python testi geçti                     |
| Vision ve görüntü | Qwen3-VL yolu; tek CUDA FLUX.1-schnell üretim/düzenleme/iptal/toparlanma                                        | Önceki frozen RTX 5070 adayında gerçek yerel kabul                                                            |
| Dashboard         | CUDA görüntü kapasitesini cihaz başına değerlendirme; Mac yolu korunur                                          | 9 test ve üretim build geçti                                                                                  |
| CI                | Hosted Windows CPU/type/Rust/UI işleri ve ayrı fiziksel GPU/küme workflow'u                                     | GitHub işleri başladı; sonuçlar henüz doğrulanmadı                                                            |

Python kontrolü: **668 geçti, 8 atlandı, 190 slow dışlandı**. Windows Python tip,
Ruff lint/format ve masaüstü tip kontrolleri geçti. Dashboard tip kontrolündeki
15 hata/6 uyarı, aynı bağımlılıkla eski `931e0ff4` tabanında da var; dashboard
tip kontrolü geçti olarak gösterilmez. Nix bu bilgisayarda yok; ilgili biçim
araçları doğrudan çalıştırıldı.

Mac Swift kaynakları değiştirilmedi; Metal/JACCL yolu ve Darwin MLX pin'i korundu.
Gerekli ortak Python düzeltmeleri ayrı Mac regresyonlarıyla kontrol edildi.

## GitHub üzerinden takip

| Commit                                                     | Değişiklik                                                  |
| ---------------------------------------------------------- | ----------------------------------------------------------- |
| [899324be](https://github.com/ovurrsl/exo/commit/899324be) | Patch baytlarını koruma ve yerel çıktıların hariç tutulması |
| [28c93dec](https://github.com/ovurrsl/exo/commit/28c93dec) | Taşınabilir CUDA runtime ve frozen dosya doğrulaması        |
| [15651dbb](https://github.com/ovurrsl/exo/commit/15651dbb) | CUDA yeterlilik kontrolü ve karma küme toparlanması         |
| [0abe5346](https://github.com/ovurrsl/exo/commit/0abe5346) | Süreç sahipliği ve async ayar penceresi                     |
| [11d15d60](https://github.com/ovurrsl/exo/commit/11d15d60) | Model belleği hatasında tam eksik miktar                    |
| [e6c21f31](https://github.com/ovurrsl/exo/commit/e6c21f31) | Mac panel düzeni, renkleri ve simgesi                       |
| [ca6c4da7](https://github.com/ovurrsl/exo/commit/ca6c4da7) | Windows görüntü modeli kapasite hesabı                      |
| [abe3fdbb](https://github.com/ovurrsl/exo/commit/abe3fdbb) | Windows CI, fiziksel kabul ve inceleme belgeleri            |

Hepsi [fork windows-native dalına](https://github.com/ovurrsl/exo/tree/windows-native)
gönderildi. Upstream'e merge veya kararlı yayın yapılmadı.

## Şu anda süren işler

1. Önceki runtime'ın native kapıları ve bütünlük doğrulaması geçti; masaüstü/NSIS
   kurucusu dosya kilidiyle başarısız oldu. Bu snapshot engine SHA-256:
   `0412c817a9628ef63a833c47c143fc871b0a62c5c2ba4308dc90b1c7ed2cb363`.
   Yeni manifest SHA-256:
   `52d6f804b53121d846d1b59a11f7d519febc9d7aabac17eece9d1272058d0f67`.
   Yeni kurucu ve native Settings kabulü henüz tamamlanmadı.
2. EXO upstream'in mevcut **280 dalının incelemesi tamamlandı**. Her dalın amacı,
   `main` farkı, commit/dosya kanıtı ve Windows katkısı
   [ayrı raporda](upstream-branches-20261010.md). Dallardaki kodlar çalıştırılmadı;
   otomatik cherry-pick/merge yapılmadı.

## Sıradaki işler

1. Yeni binary'de gerçek Windows ayar penceresinin dolu açılmasını, beş sekmeyi,
   pencere reuse/klavye/modal akışını ve API'nin çalışmasını doğrulamak.
2. Yeni kurucuyu ayrı Unicode dizinine kurup paket bütünlüğü, GPU sohbeti,
   düzgün kapanış, orphan worker ve model korumalı kaldırmayı tekrar doğrulamak.
3. Yeni engine/manifest/installer hash'lerini ve kabul kapsamını rapora kaydetmek.
   Eski kabul sonuçları otomatik olarak yeni binary'ye aktarılmayacak.
4. Güncel kaynakların gerekli fiziksel PC–Mac tekrarlarını ve uzun context/cache
   testlerini tamamlamak; iki cihazdan sonra üç cihaz matrisine geçmek.

## Bekleyen kabul ve yayın şartları

| Bekleyen                                              | Sebep / gerekli kaynak                                                                                              |
| ----------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Temiz fiziksel Windows                                | Bu PC geliştirme araçları içeriyor; son kullanıcı kurulumunu tek başına kanıtlamaz                                  |
| İkinci M1 ve üç cihaz                                 | Önceki fiziksel kabul RTX 5070 + tek M1 kapsamındadır                                                               |
| Native DPI ve erişilebilirlik                         | Tarayıcı piksel yoğunluğu testleri gerçek Windows monitör/klavye kabulünün yerine geçmez                            |
| Uzun context ve tüm bellek/failure matrisi            | Kısa sohbet başarısı bütün sınır koşullarını kapsamaz                                                               |
| Karma tensor parallelism, prefill ve görüntü pipeline | Tek CUDA görüntü/vision ve iki cihaz text PP kabulü ileri karma özellikleri kanıtlamaz                              |
| İmzalı kurulum/güncelleme                             | Üretim imza anahtarı ve sertifika henüz yapılandırılmadı; yerel aday imzasız                                        |
| Repo güvenlik denetimi                                | Codex Security önceki çalışmasında kaynak kapsamı 0/911, helper/setup hataları; 0 bulgu güvenli repo demek değildir |
| MLX P2 socket retry sızıntısı                         | Eski upstream kaynakta başarısız bağlantı denemeleri socket kapatmıyor; ayrı patch/wheel ve tekrar kabulü gerekli   |
| NVIDIA kapsamını genişletme                           | Güncel `+win.3` yalnız `120a-real;120-virtual`, hedef RTX 5070; diğer nesiller/çoklu GPU kabul edilmedi             |

## Model yükleme hatasının durumu

`Required: 8.3GB, Available: 8.3GB` gerçek bayt değerlerinin yuvarlanmasından
kaynaklanıyordu. Mesaj düzeltildi; VRAM sınırı kaldırılmadı. Denenen
`mlx-community/gemma-4-e4b-it-8bit` yaklaşık 8,35 GiB ağırlık gerektiriyor;
Windows'un 2,5 GiB rezervi ve diğer uygulamaların VRAM kullanımı hesaba katılıyor.
Bu modelin başarıyla çalıştığı iddiası yok: önceki izole native testte offline
mod açıktı ve dosyaları yerel cache'te yoktu. Uygun precision/gerçek boş bellek
ve eşleşen fork sürümündeki Mac katılımı ayrıca doğrulanmalıdır.

## Kullanılan incelemeler

Superpowers doğrulama/plan yürütme ve bağımsız kod incelemeleri; GitHub API ve
yerel immutable commit karşılaştırması kullanıldı. Claude'un 26 commit/37 dosyalık
eski Windows çalışması [ayrı raporda](windows-claude-baseline-review.md).
Context7 güncel bağımlılık belgeleri gereken işlerde yararlıdır; durum sayıları
yerel test kanıtlarından gelir. Bu rapor yeni bir Codex Security taraması değildir.
