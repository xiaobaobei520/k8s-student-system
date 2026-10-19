import os, time, pycdlib

SRC = r"D:\k8sstudey\Rocky-9.6-x86_64-minimal.iso"
DST = r"D:\k8sstudey\Rocky-9.6-ks.iso"
KS  = r"D:\k8sstudey\ks\ks.cfg"
CFG = r"D:\k8sstudey\ks\grub.cfg"

NEW_CFG = """set default=0
set timeout=1

function load_video {
  insmod efi_gop
  insmod efi_uga
  insmod video_bochs
  insmod video_cirrus
  insmod all_video
}
load_video
set gfxpayload=keep
insmod gzio
insmod part_gpt
insmod ext2

search --no-floppy --set=root -l 'Rocky-9-6-x86_64-dvd'

menuentry 'Install Rocky Linux 9.6' --class fedora --class gnu-linux --class gnu --class os {
\tlinuxefi /images/pxeboot/vmlinuz inst.stage2=hd:LABEL=Rocky-9-6-x86_64-dvd inst.ks=cdrom:/ks.cfg inst.text console=ttyS0,115200 console=tty0
\tinitrdefi /images/pxeboot/initrd.img
}
"""
open(CFG, 'w', newline='\n').write(NEW_CFG)

t0 = time.time()
iso = pycdlib.PyCdlib()
iso.open(SRC, mode='rb')
iso.rm_file('/EFI/BOOT/GRUB.CFG;1')
iso.add_file(CFG, iso_path='/EFI/BOOT/GRUB.CFG;1', rr_name='grub.cfg', joliet_path='/EFI/BOOT/grub.cfg')
print("replaced /EFI/BOOT/grub.cfg")
iso.add_file(KS, iso_path='/KS.CFG;1', rr_name='ks.cfg', joliet_path='/ks.cfg')
print("added ks.cfg")
iso.write(DST)
iso.close()
print("ISO written (%.1fs)" % (time.time() - t0))

iso = pycdlib.PyCdlib()
iso.open(DST, mode='rb')
cat = iso.eltorito_boot_catalog
for sec in cat.sections:
    for e in sec.section_entries:
        print("UEFI entry platform=0x%02x lba=%s sectors=%s" % (sec.platform_id, e.load_rba, e.sector_count))
iso.get_file_from_iso(r"D:\k8sstudey\ks\_chk_grub.cfg", iso_path='/EFI/BOOT/GRUB.CFG;1')
iso.get_file_from_iso(r"D:\k8sstudey\ks\_chk_ks2.cfg", iso_path='/KS.CFG;1')
iso.close()
g = open(r"D:\k8sstudey\ks\_chk_grub.cfg").read()
print("--- verified grub.cfg ---")
print(g)
print("ks.cfg bytes:", os.path.getsize(r"D:\k8sstudey\ks\_chk_ks2.cfg"))
print("ISO %.2f GB" % (os.path.getsize(DST) / 1024**3))
