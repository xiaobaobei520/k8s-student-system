import pycdlib, os, time

src = r"D:\k8sstudey\Rocky-9.6-x86_64-minimal.iso"
dst = r"D:\k8sstudey\Rocky-9.6-ks.iso"
ks  = r"D:\k8sstudey\ks\ks.cfg"

# 极简引导配置：无菜单、1 秒超时、直接带 kickstart 参数 + 串口控制台
BOOT_CFG = b"""default linux
timeout 10
prompt 0
label linux
  kernel vmlinuz
  append initrd=initrd.img inst.stage2=hd:LABEL=Rocky-9-6-x86_64-dvd inst.ks=cdrom:/ks.cfg inst.text console=ttyS0,115200 console=tty0
"""

t0 = time.time()
iso = pycdlib.PyCdlib()
iso.open(src, mode='rb')
print("opened source, RR=%s Joliet=%s" % (iso.has_rock_ridge(), iso.has_joliet()))

cfg = r"D:\k8sstudey\ks\isolinux.cfg"
open(cfg, 'wb').write(BOOT_CFG)
iso.rm_file('/ISOLINUX/ISOLINUX.CFG;1')
iso.add_file(cfg, iso_path='/ISOLINUX/ISOLINUX.CFG;1',
             rr_name='isolinux.cfg', joliet_path='/isolinux/isolinux.cfg')
print("replaced isolinux.cfg")

iso.add_file(ks, iso_path='/KS.CFG;1', rr_name='ks.cfg', joliet_path='/ks.cfg')
print("added ks.cfg")

print("writing ...")
iso.write(dst)
iso.close()

# 回读校验
iso = pycdlib.PyCdlib()
iso.open(dst, mode='rb')
iso.get_file_from_iso(r"D:\k8sstudey\ks\_chk_cfg", iso_path='/ISOLINUX/ISOLINUX.CFG;1')
iso.close()
print("--- verified isolinux.cfg in new ISO ---")
print(open(r"D:\k8sstudey\ks\_chk_cfg").read())
print("done in %.1fs, size=%.2f GB" % (time.time() - t0, os.path.getsize(dst) / 1024**3))
