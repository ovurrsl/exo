# EXO dal entegrasyonu — 10 Ekim 2026

Kullanıcı, yararlı upstream dallarının Windows/NVIDIA çalışmasına uygulanmasını ve `ex-exo` deposuyla dallarının incelenmesini istedi. Yetki mevcut `windows-native` dalında adım adım test, commit ve fork'a push kapsamındadır. Ana dala merge veya yayın yapılmayacak.

## Bağlayıcı sınırlar

- Mac Swift kaynakları, Metal/JACCL yolu ve Darwin MLX kaynağı/pinleri korunur.
- Varsayılan API portu 52415 ve mevcut ortak mesaj şemaları korunur.
- Mevcut Windows VRAM rezervi, CUDA kabul probu, eşgüdümlü cache eviction ve sahip olunan süreç kapanışı korunur.
- Dal adından özellik çıkarsamak yerine sabit commit'in gerçek farkı değerlendirilir. Büyük dal geçmişleri bütünüyle birleştirilmez; gerekli düzeltmeler seçilir veya uyarlanır.
- Apache-2.0 mevcut EXO ile GPL-3.0 arşiv `ex-exo` kodu otomatik birleştirilmez. Eski depodan doğrulanmış tasarım/test fikirleri bağımsız uygulanabilir.
- Kaynak testleri, gerçek GPU/küme ve temiz kurulum kabulü ayrı kanıtlardır. Önceki installer yeni kaynak değişikliklerinin kabul kanıtı olamaz.

## Uygulama sırası

1. Güncel EXO'nun 280 dalını mevcut fork ile karşılaştır; arşiv `ex-exo`nun 120 dalının amaçlarını ve faydasını kaydet. Entegrasyon matrisi kaynak SHA, karar, gerekçe ve kanıt içersin.
2. API: görüntü runner hatasının API'yi düşürmesini, başarısız yerleştirmenin sessiz kabulünü, erken kapanan akışları ve non-stream hata durumunu anlamlı başarısız testlerle doğrula; uyumlu düzeltmeleri uygula.
3. İndirme/model yolları: iptal sonrası tekrar, durum toparlanması, güvenli model kimliği ve yerel dosya doğrulaması düzeltmelerini mevcut davranışla karşılaştırıp uygula.
4. Küme/lifecycle: pipeline iptali, ring abort, yüklenen instance belleği, silinmiş runner/task durumu ve keşif toparlanmasını mevcut Windows kapanış/timeout akışını koruyarak düzelt.
5. Model/cache: prefix snapshot çoğalması, CPU prefix karşılaştırması, detokenizer tekrar kullanımı ve decode belleği düzeltmelerini Windows collective sırasını koruyarak değerlendir ve test et.
6. Protokol değiştiren snapshot/election/transport yeniden yazımları ve alternatif Linux/CUDA backend'leri için bağımlılık ve kabul şartlarını açıkça kaydet; yarım veya donanıma uymayan çalışmaları etkinleştirme.
7. Zorunlu kontrolleri çalıştır: Python strict type check, Ruff lint/format, test paketi; değişen Rust/UI kapsamı için ilgili derleme ve test. Nix yoksa eşdeğer biçim araçları kullanılır ve raporda belirtilir.
8. Kullanıcının son talebine göre her uyumlu değişiklik grubunu ayrı `work/*` konu dalında, kaynak commit atfıyla commit ve fork'a push et. Test ve inceleme sonrasında bu dalları `windows-native`e birleştir. Önceden gönderilmiş API commit'lerini yeniden yazma; `work/upstream-api-errors` dalında da izlenebilir tut. GitHub CI sonucunu kontrol et; gerçek hataları adlarıyla raporla ve mümkünse düzelt.
9. Son kapsamı bağımsız kod incelemesine ver, önemli bulguları başarısız test → düzeltme → geçen test akışıyla gider.
10. Arşiv dal raporunu, entegrasyon matrisini ve mevcut kabul sınırlarını GitHub'da erişilebilir şekilde tamamla.

## Kontrol ve inceleme odağı

Her kod adımı önce mevcut hatayı göstermeli, sonra aynı testi geçirmeli. Önemli sınırlar: istemci iptali ile runner çökmesini ayırmak; CUDA image rezervini disk boyutuyla değiştirmemek; loading ile gerçek bellek ölçümünü iki kere saymamak; cache kolektif sırasını ayırmamak; Windows uzun/Türkçe yolları ve çoklu model dizinlerini korumak; Mac-only davranışa etkileri açıkça belirtmek.

İlerleme ve karar defteri: `build/acceptance/upstream-integration-progress-20261010.md`. Nihai kararlar ve tamamlanmayan kabul testleri kalıcı entegrasyon raporuna taşınır.

## Eklenen gereksinimler

Claude ortak imzalı fork dalları da değişmez SHA ve ortak tabanlarından incelenir. Mac ile PC'nin doğrudan Thunderbolt/USB4 kablosu üzerinden TCP ring ile iletişimi hedeflenir; M1 üzerinde TB5 RDMA ilan edilmez. Kullanıcı kablonun bağlı olduğunu, türünü bilmediğini belirtti. Windows USB4 P2P ve Mac Thunderbolt Bridge arayüz/IP/rota tespiti, ardından bu arayüzlerden gerçek ring ve model testi gerekir.

VRAM'e sığmayan model için PC sistem RAM'i kullanımı ayrı offload geliştirme kapsamıdır. NVML hatasında host RAM'i GPU kapasitesi gibi ilan etmek veya CUDA rezervini kaldırmak bu gereksinimi karşılamaz. Mevcut görüntü aşamalarının host ağırlıkları ile metin modelinin henüz olmayan katman offload'u ayrılır. Sabit MLX CUDA allocator/transfer davranışı incelenir; host ve GPU bütçeleri, yükleme zirvesi, KV/workspace, stream sırası, ring ve Mac regresyonları test edilmeden büyük modellerin çalışacağı ilan edilmez.

Founder/design ajanının kaynak ve ekran görüntüsü incelemesi Mac renklerini/düzenini koruyan ayrı Windows arayüz düzeltmelerine yön verir. Yeni kurulan beceriler görevlerine göre kullanılır; kurulum tamamlanması yeni bir güvenlik taramasının tamamlandığı anlamına gelmez.
