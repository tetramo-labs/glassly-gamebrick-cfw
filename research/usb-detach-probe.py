import usb.core,usb.util,usb.backend.libusb1
b=usb.backend.libusb1.get_backend(find_library=lambda _: '/opt/homebrew/lib/libusb-1.0.dylib')
d=usb.core.find(idVendor=0x4c4a,idProduct=0x3442,backend=b)
if d is None: raise SystemExit('Controller bootloader not present')
d.default_timeout=2000
print('Checking driver',flush=True)
print('Kernel active:',d.is_kernel_driver_active(0),flush=True)
print('Detach',flush=True)
try:
 d.detach_kernel_driver(0)
 print('Detached',flush=True)
 usb.util.claim_interface(d,0)
 print('Claimed',flush=True)
 usb.util.release_interface(d,0)
finally:
 usb.util.dispose_resources(d)
