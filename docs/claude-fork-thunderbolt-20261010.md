# Claude fork dalları ve Windows–M1 Thunderbolt incelemesi — 10 Ekim 2026

İncelenen sabit kaynak: `ff98381010c3792319d760eb7b17cb0dbcb87fa5` (`windows-native`). Fork: `https://github.com/ovurrsl/exo`. GitHub üzerinden 14 canlı dal ve her dalın SHA değeri doğrulandı; tüm yerel fork refs eşleşti. `git ls-remote` sandbox DNS-thread hatası verdiği için GitHub read-only branch/compare API kullanıldı; fetch, ref, source veya çalışan uygulama değişikliği yapılmadı. Yerel JSON tüm SHA, merge-base, unique commit, Claude coauthor/session trailer ve dosya listesini içerir. Bu 14 dal, incelemenin başlangıç anındaki sonlu fork snapshotıdır; sonradan oluşturulan work/\* dalları [entegrasyon raporunda](upstream-integration-20261010.md) ayrı gösterilir.

**Fiziksel Thunderbolt-IP kabulü geçmedi.** Ana ajan OS probunda Windows USB4/TB P2P NIC bulunamadı; I226V Ethernet 1Gbps Up, Wi-Fi disconnected, Microsoft USB4 host/root router StatusOK. M1 Thunderbolt en1/en2 inactive, bridge0 yok; PC rotası en0 Wi-Fi. Kullanıcı kablonun USB4/Thunderbolt portunda olduğunu ve kabloya güvendiğini doğruladı; kesin kablo modeli henüz kayda alınmadı. Yanlış port veya bozuk kablo teşhisi yapılmadı. Bu gözlem henüz ağ tüneli kurulmadığını gösterir; eksik OS NIC’i yazılım etiketi veya dal merge’i oluşturamaz. Mac kanıtı: `build/acceptance/thunderbolt-mac-network-20261010.log` yerel ağ probu. Ham donanım/ağ kayıtları yerel kabul dizininde tutulur; donanım kimlikleri yayımlanmaz.

## Her canlı fork dalı için sonlu karar

| Dal                              | Sabit uç SHA                               | Current/dal unique commit | Claude metadata commit | Karar                               |
| -------------------------------- | ------------------------------------------ | ------------------------: | ---------------------: | ----------------------------------- |
| `docs/test-setup-workspace`      | `ffcb9850b7d994ec932da7f745641e94b08b2679` |                      37/1 |                      1 | Belge portu                         |
| `docs/zenoh-namespace-env`       | `6173d926686645064cb77aabf72202a5b4cb9edb` |                      37/1 |                      1 | Belge portu                         |
| `feat/2010-badge-and-nic-speeds` | `e9a9fba32c7cfb625ce119e23b08242a1e669841` |                     71/20 |                     12 | Toplu merge ertelensin              |
| `feat/local-process-cluster`     | `9ec39397ad6c3fe0a8dde46a2317efca371c4024` |                      37/2 |                      2 | Uyarlanmış test aracı portu         |
| `feat/model-card`                | `5836ccef473c8fc5197c57dc60e4ffdccfbad420` |                      37/1 |                      1 | Model kartı port adayı              |
| `feat/nic-link-speed`            | `d0a422d9baf2b305c08d5cca088c6731f004b2f3` |                      37/3 |                      3 | Ortak protokol nedeniyle ertelensin |
| `fix/model-id-traversal`         | `448a2ecafe8004c94d71bb0798dee173c8d735e0` |                      37/1 |                      1 | Güçlendirilmiş tek port             |
| `fix/ssrf-image-url`             | `602af33aab13eeaa4f3fb6dbe96109a7779ea2b4` |                      37/2 |                      2 | Güçlendirilmiş tek port             |
| `main`                           | `21a54c5ea0230a3bec1e1a786d200126c7e34ec6` |                      37/0 |                      0 | Zaten kapsanmış                     |
| `upstream-2010-base`             | `d1f4b24d5e660af8467e24d5109c6e487b3b7cf6` |                     71/13 |                     10 | Profiler protokolü ertelensin       |
| `windows-native`                 | `ff98381010c3792319d760eb7b17cb0dbcb87fa5` |                       0/0 |                     26 | Tamamen mevcut                      |
| `windows-native-backup`          | `f83239c34302514073d1c7d7ce8561305032e53c` |                      37/4 |                      1 | Eski uygulama yenilenmiş            |
| `windows-native-phase2`          | `c4e2740791a3d97705aa48de701a121b6e52b4c1` |                    20/157 |                    113 | Toplu merge ertelensin              |
| `work/upstream-api-errors`       | `ff98381010c3792319d760eb7b17cb0dbcb87fa5` |                       0/0 |                     26 | Tamamen mevcut                      |

Claude sayıları upstream ortak tabandan gelen ancestry metadata sayısıdır; phase2 içindeki113, yerel forkta113 ayrı yeni özellik yazıldığını ifade etmez. `main`, `windows-native` ve `work/upstream-api-errors` mevcut taban/aynı uç olarak ayrıca kontrol edildi.

**Merge-base:** Ana dallar `21a54c5ea0230a3bec1e1a786d200126c7e34ec6`; badge ve upstream-2010 `8dae3ecb9a58cd169723e064560dd05e5d5672f3`; phase2-current `5486e20441ed6095e53a731ee27c1e8d37927097`; native ve work-api current SHA. JSON her dal için upstream-main ve current tabanını ayrı verir.

- **docs/test-setup-workspace:** --all-packages eksik. AGENTS/CONTRIBUTING portu; Windows extra örneğini CUDA kılavuzuna uyarla.
- **docs/zenoh-namespace-env:** README dört yerde eski EXO_LIBP2P_NAMESPACE diyor. Tek README portu uygundur.
- **feat/2010-badge-and-nic-speeds:** 13 upstream profiler commiti üzerine iki üretim badge/NIC commiti ve beş geçici screenshot commiti. Profil/state şeması değişir; 40Gb/s -> TB4 çıkarımı M1 TB3 için yanlış. TCP edge için düğümün en hızlı portunu seçmek gerçek kabloyu kanıtlamaz.
- **feat/local-process-cluster:** İki yeni tools dosyası, ortak protokol değişmez. Windows process group/CTRL_BREAK, port/namespace/EXO_HOME ayrımı yararlı. \_stop_node process=None atamasını gerçek çıkıştan sonra yap; başarısız force-stop sahipliğini sakla. Tam lifecycle ve izole gerçek süreç kabulü gerekir.
- **feat/model-card:** Qwen3-4B-4bit mevcut ModelCard şemasında doğrulandı ve kaynakta yok. Gerçek CUDA/Metal yükleme, snapshot ve sampling kabulü gerekir; supports_tensor CUDA tensor kapısını açmaz.
- **feat/nic-link-speed:** İki yeni NetworkInterfaceInfo alanı eski FrozenModel extra_forbidden ile reddediliyor. Hız okuyucularını yalnız yerel diagnostics alanına uyarlamak mümkündür. Windows supported-speed okuyucu yok; macOS ifconfig donanım doğrulaması eksik.
- **fix/model-id-traversal:** Mevcut ModelId.normalize yalnız slash değiştiriyor, delete_model containment yok. Fork düzeltmesi Windows drive/colon/reserved adları ve cache silme containment kapsamını tam kapatmaz. Güçlü upstream path portuyla tek validator kullan.
- **fix/ssrf-image-url:** Mevcut fetch_image_url public-address veya redirect kontrolü yapmıyor. Fork pre-DNS kontrolünden sonra aiohttp yeniden çözüyor; rebinding boşluğu var. Resolver/bağlantı IP doğrulaması ve API400 kapsamıyla tamamlanmalı.
- **main:** Current native tabanı; unique commit yok.
- **upstream-2010-base:** Alex #2010 profiler tabanı; native Windows transport eklemez. Yeni GPU/link state/API alanları ve Mac RDMA probe süreçleri. M1 TB5 RDMA şartını sağlamaz.
- **windows-native:** İnceleme HEAD ile aynı SHA; Claude baseline Windows pipes/pidfile/NIC/Winsock işleri korunur.
- **windows-native-backup:** main tabanından dört alternatif eski Windows commit. Process/yol/NIC/discovery/MLX işleri current native uygulamasında daha yenidir. Eski mDNS veya bağımlılık/pin/bellek yaklaşımını geri alma.
- **windows-native-phase2:** Base5486e204, dalda157/currentta20 unique commit. Upstream staging/merge agregasyonu; Swift, heartbeat/snapshot, lifecycle/QoS, cache/generator değiştirir. Önceki raporlardan minimal commitleri seç. Runner boşluğu graceful ack değildir. Swift bridge restore ve Darwin pin değişimi kapsam dışı.
- **work/upstream-api-errors:** windows-native ile aynı ff9838; unique commit yok.

## Minimal portların kaynağı ve bağımlılık sırası

1. README namespace düzeltmesi `6173d926686645064cb77aabf72202a5b4cb9edb` → test workspace belgeleri `ffcb9850b7d994ec932da7f745641e94b08b2679`; Windows kurulum örneğini mevcut CUDA extra ile uyarla.
2. İsteğe bağlı test aracı: `36a7fdded50e59c5c25f9ca1acf191f1dc60d56b` → `9ec39397ad6c3fe0a8dde46a2317efca371c4024`; yalnız `tools/src/exo_tools/local_cluster.py` ve `tools/src/exo_tools/tests/test_local_cluster.py`. Sahipliği gerçek process exit ile doğrulayan stop uyarlaması ve tam lifecycle kabulü gerekir.
3. Model kartı `5836ccef473c8fc5197c57dc60e4ffdccfbad420`, yalnız `resources/inference_model_cards/mlx-community--Qwen3-4B-4bit.toml`; current model schema geçiyor. Gerçek backend/model kabulü olmadan yeni qualification iddiası yok.
4. Güvenli yol/SSRF adayları yukarıdaki eksikleriyle tek güçlendirilmiş port olarak değerlendirilmeli. ModelId `448a2ecafe8004c94d71bb0798dee173c8d735e0`; SSRF üretim `6677071d231301721455637240cf358c29c87e1e` ve API400 tamamlayıcısı `602af33aab13eeaa4f3fb6dbe96109a7779ea2b4` JSON unique commit listesinde.
5. NIC speed sırası `fb88bc778562241450898ea95ff1180ec4570e8b` → `989e2482fd6844017c2e22cea3a12d6ec9610deb` → `d0a422d9baf2b305c08d5cca088c6731f004b2f3`; current shared payload korunurken sadece yerel diagnostic okuyucu uyarlanabilir.
6. Badge üretim SHA `a43b5c7e551703ea238d283ff3d387769095ff82` → `9c20ac4012df9c8c3cdcc7875983dae36efda133`, profiler base `d1f4b24d5e660af8467e24d5109c6e487b3b7cf6`. Tam patch ortak profile/state alanları ve eski base’e bağlı; önceki transport tipiyle şemasız `Thunderbolt TCP` etiketi ayrı port olabilir. 40Gb/s’den TB3/TB4 ayrımı yapma.
7. Phase2 toplam merge yerine önceki `upstream-integration-cluster-20261010.*` ve `upstream-integration-model-20261010.*` raporlarındaki immutable minimal kaynakları kullan. Runner state erken kaldırılması graceful shutdown acknowledgement yerine geçmez; QoS/discovery command retry/event replay ve Windows/Mac rebuild kabulü bitmeden ertelenir. Swift bridge restore, Darwin MLX pin ve mevcut JACCL/Metal yolları korunur.

## Mevcut kaynak TCP kablo için ne yapıyor?

`22b11afeb8566b89387b69dd87e4146c7796581f` mevcut native ancestry içindedir. `src/exo/utils/info_gatherer/system_info.py` Windows registry DriverDesc üzerinden USB4(TM) P2P Network Adapter ve Thunderbolt(TM) Networking’i `thunderbolt` olarak sınıflar. Thunderbolt dock Ethernet fixture’i `ethernet`; okunamayan registry friendly-name fallback. `usb4` regex genel olduğundan USB4 içeren generic dock açıklaması için negatif kontrol gerekir. Gerçek NIC yokken sınıflayıcı yeni bir adapter yaratmaz.

`src/exo/master/placement_utils.py::find_ip_prioritised` ring için Thunderbolt → maybe_ethernet → Ethernet → Wi-Fi → unknown tercih eder. JACCL coordinator Ethernet’i tercih eder. Yalnız topology’deki ulaşılabilir SocketConnection IP’leri adaydır; nominal NIC hızı sıralama ölçütü değildir. `net_profile.py` advertised IP’ye HTTP/node_id ile kimlik doğrular; source-interface bind yapmaz. Hostfile seçimi, OS rota ve socket/counter çıktısı gerçek kablo taşımasını birlikte kanıtlamalı. Windows özel ThunderboltBridge diagnostic cycle’ına girmese de general TCP SocketConnection ring kablo IP’siyle çalışabilir.

## Thunderbolt/IP, donanım ve gerçek durum

Windows USB4NET Ethernet-over-USB4 protokolü TB3 ile geriye uyumludur ve bağlantı kurulunca P2P network adapter/link-local169.254/16 verir; Microsoft TB3/USB4 kabloyu açıkça tarif eder. Bu Mac–Windows TCP bağlantısını teknik olarak mümkün kılan sözleşmelerden biridir. [Microsoft USB4NET](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/usb4-interdomain-connections)

Apple Mac-Mac IP-over-Thunderbolt için Thunderbolt Bridge service ve manual IPv4 ayarını belgeler. Çapraz OS uyumluluğu bu iki resmî sözleşmeden yapılan **koşullu çıkarımdır**; bu PC–M1 çiftinin sertifikası veya mevcut kablonun çalıştığı kanıtı değildir. [Apple Thunderbolt-IP](https://support.apple.com/guide/mac-help/ip-thunderbolt-connect-mac-computers-mchld53dd2f5/mac)

M1 Air2020 portları TB3/USB4 en fazla40Gb/s. Apple RDMA macOS26.2 ve Apple-silicon TB5 gerektirir; M1 daha yeni OS veya TB5 kablosuyla JACCL/TB5 RDMA kazanmaz. Burada gereken TCP ring hedefidir. [Apple M1 özellikleri](https://support.apple.com/en-us/111883), [Apple TN3205](https://developer.apple.com/documentation/technotes/tn3205-low-latency-communication-with-rdma-over-thunderbolt?changes=_1), [MLX ring/JACCL](https://ml-explore.github.io/mlx/build/html/usage/distributed.html)

Mevcut eksik bridge/NIC için resmî elle yapılacak inceleme yolu: Mac System Settings → Network → Action → Add Service → Interface Thunderbolt Bridge → Service Name → Create; sonra service Details → TCP/IP. Bunun yeterliliği ayrıca gerçek active link ile doğrulanır. Bu incelemede servis oluşturulmadı. [Apple service ekleme](https://support.apple.com/guide/mac-help/set-up-a-network-service-on-mac-mchlp1176/27/mac/27), [Apple Thunderbolt-IP](https://support.apple.com/guide/mac-help/ip-thunderbolt-connect-mac-computers-mchld53dd2f5/mac)

Windows Settings → Bluetooth & devices → USB → USB4 Hubs and Devices controller/attached-device capabilities’ini gösterir; controller StatusOK tek başına network tunnel kanıtı değildir. Uygun doğrudan USB4/TB portları ve sertifikalı USB4 veri kablosu veya TB3 veri kablosu doğrulanmalıdır; sırf USB-C uç biçimi yeterli kanıt değildir. Kullanıcının doğru port ve güvenilir kablo bilgisi esas alınır; sonraki kanıt host-to-host NIC’in ve active link’in oluşmasıdır. Source patch’iyle fiziksel link kurulmuş sayılmaz. [Microsoft USB4 settings](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/usb4-settings-enablement), [Microsoft USB-C troubleshooting](https://support.microsoft.com/en-us/windows/hardware/usb/fix-usb-c-problems-in-windows), [Microsoft TB3 geriye uyumluluk](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/usb4-interdomain-connections)

MLX resmî ring transport’u TCP sockets kullanır ve Thunderbolt-IP ring’i belgeler. MLX’nin Mac network setup helper’ı Windows network service kurucusu değildir; mevcut fork native CUDA/Winsock ring’inin ortak hostfile sözleşmesi korunmalı. [MLX distributed](https://ml-explore.github.io/mlx/build/html/usage/distributed.html), [MLX launching](https://ml-explore.github.io/mlx/build/html/usage/launching_distributed.html)

## Gerçekleşen doğrulama ve eksik kabul

Mevcut beş Windows NIC fixture testi, ring IP seçiminin dört kontrolü, fork local harness’in altı saf port/argv testi ve Qwen4B current schema doğrulaması geçti. NIC hız payload’ının iki eski-schema rejection kontrolü beklenen `extra_forbidden` verdi. Modüller read-only kaynaklardan bellek içinde yüklendi; gerçek node/soket başlatılmadı. Full pytest bu sandboxta Windows event-loop/soket başlangıcında ilerlemedi; kendi başlatılan komutlar durduruldu. Bu sonuç full pytest geçişi iddiası değildir.

Önceki `health-handle-final-physical-matrix-20261010.json` Mac-master, Windows-master ve Windows-stop için üçer chat/exit0 gösterir ve release_ready=false bırakır. Kaynak kabulünün bu başarısı fiziksel Thunderbolt-IP kabulüne dönüştürülemez; bugünkü route çıktısı Wi-Fi gösteriyor.

Tüm aşağıdaki kapılar bekliyor:

- **cable-link:** Bilinen TB3/USB4 veri kablosu doğrudan uygun portlar; Windows USB4NET/P2P NIC, Mac Thunderbolt iface active.
- **ip-route:** Gerçek cable IP/subnet, her iki peer rota, intended NIC ile TCP/ping; IPv6 discovery korunur. Mac bridge servis oluşturma ayrı OS işlemi.
- **exo-selected-route:** Aynı source/protocol snapshots; namespace/discovery/node_id; ring hostfile gerçek cable IP. Soket/route/sayaç Wi-Fi/Ethernet fallback olmadığını kanıtlar.
- **ring-both-ranks:** scripts/windows/check_mixed_ring.py gerçek cable PC IP ile her iki rank sırası, collective veri kontrolleri, owned clean exit.
- **model-both-masters:** Aynı model revision/hash; compatible CUDA/Metal runtime; Mac-master/Windows-master üç sohbet, cancellation/delete/stop ve exit0; child/port yok.
- **reconnect-and-three-device:** Uzun üretimde cable çıkar/tak bounded fail/recovery; zombie/GPU kalmaz; ikinci M1 ile gerçek üç cihaz topology daha sonra.
- **new-test-tool:** tools/src/exo_tools/tests/test_local_cluster.py tüm26 fake lifecycle testi, gerçek izole Windows/Mac discovery/reconnect, CTRL_BREAK child propagation, port çakışmaması, process ownership exit sonrası.
- **profiler-and-discovery:** NIC hızını current ortak payload dışında yerel diagnostics tut; profiler shared rollout mevcut kapsam dışında. QoS/discovery için retry/replay end-to-end ve iki platform rebuild olmadan alma.

Başvurulacak test/export paths: mevcut NIC testleri `src/exo/utils/info_gatherer/tests/test_windows_system_info.py`; ring selection `src/exo/master/tests/test_placement_utils.py` + explicit mixed-interface controls; yeni araç `tools/src/exo_tools/tests/test_local_cluster.py`; fiziksel controller `scripts/windows/check_mixed_ring.py`; mevcut kabul `docs/windows-hardware-acceptance.md`. Yeni fiziksel çıktı ayrı timestamp/namespace directory’sine yazılmalı, model/runtime/source/route hashes birlikte tutulmalı. Bu incelemenin kalıcı exports yalnız bu `.md` ve eş `.json` dosyalarıdır.

## Gerçek anakart ve BIOS belgesiyle teşhis

Salt okunur WMI probu **ROG STRIX Z890-I GAMING WIFI**, BIOS **3202 (2026-04-29)** ve Microsoft USB4 driver **10.0.29683.1000** saptadı. ASUS bu modele iki entegre Intel Thunderbolt4 USB-C portu tanımlar. M1 ile hedef TB3 uyumlu IP bağlantısıdır. [ASUS bu kartın özellikleri](https://rog.asus.com/au/motherboards/rog-strix/rog-strix-z890-i-gaming-wifi/spec/)

Kullanıcının verdiği [ASUS Z890 BIOS belgesi](https://rog.asus.com/motherboards/rog-strix/rog-strix-z890-i-gaming-wifi/helpdesk_manual/) (kullanıcının sağladığı E25597 PDF) ana ajanca çıkarılıp72–75 sayfalar render edildi; bu incelemede ilgili extracted text de okundu. `build/acceptance/asus-z890-thunderbolt-manual-20261010.json` yerel metin kanıtı ve `build/acceptance/asus-z890-manual-pages-20261010` görselleri retained. Sayfa72 **Advanced → Thunderbolt(TM) Configuration** bölümünde **Integrated Thunderbolt Enable** ile **USB4 CM Mode: Software CM / CM Debug** vardır; sayfa73 entegre root port0/1 ayarlarını verir. Gerçek BIOS değerleri yalnız okunup karşılaştırılmalı; OS router StatusOK iken bunların kapalı olduğu varsayılamaz. PCIe Tunneling ayrı özellik olarak listelenir; mevcut TCP-IP tüneli kabulünün yerine geçen bir ayar olarak önerilmez.

Sayfa74 **USB4 Host Router Class Code** yalnız **Thunderbolt5 Enable** altındadır; bu entegre TB4 anakart için ilgiliymiş gibi önerilmez. **ASM4242** ayrı USB4 add-on card bölümüdür; gerçek integrated Intel controller için onun ayarlarını kullanma. **Reserved Memory / Reserved PMemory** root-bridge PCIe adres rezervasyonlarıdır; NVIDIA VRAM artırma veya model RAM offload yöntemi değildir. BIOS, Mac network service veya GPU ayarı değiştirilmedi.

Sonraki resmî GUI incelemesi Windows **USB4 Hubs and Devices** sayfası ve **Device Manager → Network adapters** altında USB4NET/P2P adapter durumudur. Mac **Network → Action → Add Service → Interface Thunderbolt Bridge** ve ardından **Details → TCP/IP** mevcut servis/IPv4 durumunu kontrol eder. Kullanıcının OS servis oluşturması ayrı eylemdir; bu rapor onu gerçekleştirmedi. NIC ve link active olduğunda gerçek peer IP/subnet ve çift taraflı rota/TCP/sayaç kanıtına geçilir; bunlar sağlanmadan exo ring testi Thunderbolt testi olarak etiketlenmez.

## Sonraki salt okunur fiziksel kontrol

10 Ekim 2026 son kontrolünde Mac `system_profiler SPThunderboltDataType` iki portta da `receptacle_no_devices_connected` bildirdi. `en1`/`en2` inactive; Windows tekrarında USB4 P2P NIC yine yok. Mac servis listesinde `EXO Thunderbolt 1`/`EXO Thunderbolt 2` var, `Thunderbolt Bridge` yok. Bu, aktif eş bağlantısının henüz oluşmadığını gösterir. Kablo arızası, yanlış port veya belirli BIOS ayarı tek başına kök neden olarak saptanmadı. BIOS ve ağ ayarları değiştirilmedi.
