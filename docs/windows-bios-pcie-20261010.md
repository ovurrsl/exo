# RTX 5070 PCIe, NCASE T1 ve ASUS Z890-I BIOS incelemesi - 10 Ekim 2026

## Ölçülen durum

Anakart **ROG STRIX Z890-I GAMING WIFI**, BIOS **3202 (2026-04-29)**, GPU **RTX 5070**, NVIDIA driver **617.42**. Kullanıcı kasanın NCASE T1 olduğunu ve **PCIe 5.0 riser** kullandığını doğruladı. Güncel [NCASE kasa sayfası](https://ncased.com/collections/t-series/products/t1-sandwich-kit-black-color) da PCIe 5.0 riser içeren V2.5 kit'i listeliyor; bu sayfa tek başına kullanıcının satın aldığı revision veya kablonun fiziksel durumunu kanıtlamaz.

| NVIDIA alanı                      | Sonuç             | Anlamı                                                                                                 |
| --------------------------------- | ----------------- | ------------------------------------------------------------------------------------------------------ |
| `pcie.link.gen.gpumax`            | 5                 | Kart Gen5 destekliyor.                                                                                 |
| `pcie.link.gen.hostmax`           | 4                 | Driver mevcut kök port sınırını Gen4 bildiriyor. Gerçek BIOS seçimi henüz okunmadı.                    |
| `pcie.link.gen.max`               | 4                 | Mevcut GPU/sistem yapılandırmasının ilan edilen sınırı Gen4.                                           |
| `pcie.link.width.current` / `max` | 16 / 16           | 16 hat aktif; mevcut ölçümde x8 daralması yok.                                                         |
| Anlık link generation             | 1, 2, 4 örnekleri | Boşta hız düşebilir. Anlık Gen1 tek başına arıza kanıtı değildir. Gen5 yük altında henüz doğrulanmadı. |

Komut `nvidia-smi --query-gpu=name,pcie.link.gen.gpucurrent,pcie.link.gen.gpumax,pcie.link.gen.hostmax,pcie.link.gen.max,pcie.link.width.current,pcie.link.width.max --format=csv`. Yerel salt okunur kanıt `build/acceptance/windows-pcie-link-20261010.json`; GPU seri numarası veya kullanıcı parolası rapora alınmadı.

Bu ölçüm BIOS'ta Gen4 seçildiğini kesin olarak kanıtlamaz. BIOS hız ayarı, riser bağlantısı/sinyal bütünlüğü ve driver raporu ayrıştırılmalıdır. PCIe hızını artırmak VRAM kapasitesini artırmaz; RAM offload'u için [açık ağırlık aktarımı ve iki bellek bütçesi](windows-host-ram-offload-20261010.md) gerekir.

## Gen5 x16 için fiziksel hız anahtarı ve BIOS

Bu anakartın ROG FPS kartında **ALT_PCIE_MODE** anahtarı bulunur. [E24355 donanım kılavuzu](https://dlcdnets.asus.com/pub/ASUS/mb/LGA1851/ROG_STRIX_Z890-I_GAMING_WIFI/E24355_ROG_STRIX_Z890-I_GAMING_WIFI_EM_WEB.pdf) sayfa 26: **Auto** varsayılan hız; **1st step** Gen4 ve yeşil LED1; **2nd step** Gen3 ve sarı LED2. Gen5 hedefinde bu anahtar Auto olmalıdır. Mevcut fiziksel konumu görülmedi; fotoğraftaki genel yeşil ışık bu LED1 olarak tanımlanamaz. Donanıma dokunmadan önce PC kapatılır ve güç bağlantısı kesilir; yalnız açıkça ALT_PCIE_MODE olarak tanımlanan anahtar incelenir.

1. Yeniden başlatmada **Delete/F2**, ardından **F7** ile Advanced Mode.
2. **Advanced → System Agent (SA) Configuration → PCI Express Configuration**.
3. **PCIEX16(G5) Link Speed** değerini kontrol et. Kullanıcının doğruladığı Gen5 riser ile **Auto** ilk tercihtir; gerçekten **Gen4** seçiliyse Auto'ya alınabilir. Auto altında hâlâ Gen4 görülürse **Gen5** seçimi kontrollü deneme olabilir; kararsızlık/görüntü sorunu halinde önceki değere dönülür.
4. Yalnız hedef slot hız ayarını değiştirdikten sonra **F10** ekranında listelenen değişikliği gözden geçir. CSM, VMD, boot/storage veya voltaj ayarlarını bu hız denemesiyle birlikte değiştirme.
5. Windows'a dönüşte aynı NVIDIA alanlarını yük altında tekrar ölç; GPU max 5, configuration/host max ve actual link Gen5, width 16 hedeflenir. GPU-Z render testi de anlık güç tasarrufu durumunu ayırmak için kullanılabilir.

Bu menü yolu ve idle hız davranışı [ASUS PCIe hız doğrulama belgesinde](https://www.asus.com/support/faq/1055579/) açıklanıyor. Kullanıcının E25597 Z890 BIOS PDF'si sayfa 66-67'de System Agent/PCI Express Configuration'ı tanımlar; slot seçeneklerinin anakarta göre değişebileceğini söyler. PC BIOS'ta olduğunda uzaktan çalışan Windows ajanı görüntü/ayar doğrulaması yapamaz; bu adım kullanıcı tarafından yürütülür. Bu incelemede BIOS değiştirilmedi veya sistem yeniden başlatılmadı.

## x16 ve M.2 paylaşımı

[Bu anakartın E24355 donanım kılavuzu](https://dlcdnets.asus.com/pub/ASUS/mb/LGA1851/ROG_STRIX_Z890-I_GAMING_WIFI/E24355_ROG_STRIX_Z890-I_GAMING_WIFI_EM_WEB.pdf), sayfa 14/20/24, **M.2_2 doluyken PCIEX16(G5)'in x8 çalışacağını** açıkça söyler. M.2_1 ve M.2_2 birbirinin yerine varsayılmamalıdır. Mevcut ölçüm x16 olduğu için şu an böyle bir hat daralması saptanmadı.

Seri BIOS PDF'si sayfa 75'teki bifurcation seçenekleri tüm Z890 modellerine aynı şekilde uygulanmaz. Bu Mini-ITX kartın tek GPU slotuna, çok slotlu kart için yazılmış X8X4X4 veya GPU-with-M.2 seçeneğini varsayılarak uygulama. x16 için M.2_2 paylaşımını dikkate almak gerekir; mevcut x16 ölçümü varken SSD sökme/taşıma önerisi yok.

## Thunderbolt için ayrı kablo incelemesi

Kullanıcının fotoğrafında ROG logolu USB-C uç ve **14016-00751200** etiketi okunuyor; kullanıcı iki ucun da USB-C olduğunu doğruladı. Parça numarasından tek başına 40 Gbps/Thunderbolt certification doğrulanamadı. Bu anakartın resmi kutu içeriği, sayfa 13, USB Type-C bağlantı kablosunu **ROG STRIX HIVE II** aksesuarıyla birlikte listeler; sayfa 44 onu HIVE II ve ayrılmış arka USB portu arasında kullanmayı tarif eder. Fotoğraf ve kutudan çıkma bilgisi HIVE aksesuar kablosuyla uyumlu; kesin USB hız standardı doğrulanmış değildir.

Böyle bir aksesuar kablosunu Thunderbolt/USB4 ağ kablosu saymak için kanıt yoktur. PC-Mac testi için iki ucu USB-C, **sertifikalı Thunderbolt 3/4 veya USB4 40 Gbps veri kablosu** ve doğrudan arka Thunderbolt portları gerekir. USB-C konnektörü veya PD şarj watt'ı bu veri standardını kanıtlamaz. [Microsoft USB4 host-to-host / TB3 uyumu](https://learn.microsoft.com/en-us/windows-hardware/design/component-guidelines/usb4-interdomain-connections).

BIOS E25597 sayfa 72-73'teki Integrated Thunderbolt/USB4 CM bölümü ilgilidir; controller OS'ta hatasız görüldüğü için kapalı olduğu varsayılmadı. TB5-only veya ASM4242 addon ayarı bu integrated TB4 karta uygulanmadı. Reserved Memory/PMemory PCI köprüsü adres rezervasyonu olup model RAM offload'u değildir. Ayrıntılı [fiziksel ağ kabul kapıları](claude-fork-thunderbolt-20261010.md) korunur.

**Kullanıcının sonraki kararı:** Thunderbolt olmadan mevcut LAN üzerinden devam edilecek. Kablo/USB4NET, yeni bridge servisi ve Thunderbolt ring kabulü ertelendi. Gen5 GPU kontrolü ve gerçek host-RAM offload geliştirmesi LAN küme çalışmasından bağımsız kalır.
