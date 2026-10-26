#include <CoreFoundation/CoreFoundation.h>
#include <IOKit/IOKitLib.h>
#include <IOKit/IOCFPlugIn.h>
#include <IOKit/scsi/SCSITaskLib.h>
#include <stdio.h>
#include <string.h>
int main(void) {
 setbuf(stdout,NULL);
 io_iterator_t it=0; IOServiceGetMatchingServices(kIOMainPortDefault,IOServiceMatching("IOSCSILogicalUnitNub"),&it);
 io_service_t s;
 while((s=IOIteratorNext(it))) {
  CFTypeRef p=IORegistryEntryCreateCFProperty(s,CFSTR("Product Identification"),kCFAllocatorDefault,0);
  int match=p && CFGetTypeID(p)==CFStringGetTypeID() && CFStringCompare(p,CFSTR("UBOOT1.00"),0)==kCFCompareEqualTo;
  if(p) CFRelease(p); if(!match) { IOObjectRelease(s); continue; }
  IOCFPlugInInterface **plug=NULL; SInt32 score=0;
  IOReturn r=IOCreatePlugInInterfaceForService(s,kIOSCSITaskDeviceUserClientTypeID,kIOCFPlugInInterfaceID,&plug,&score);
  printf("SCSI plug-in result 0x%08x\n",r);
  if(!r && plug) {
   SCSITaskDeviceInterface **dev=NULL;
   HRESULT h=(*plug)->QueryInterface(plug,CFUUIDGetUUIDBytes(kIOSCSITaskDeviceInterfaceID),(LPVOID*)&dev);
   printf("QueryInterface 0x%08x\n",(unsigned)h);
   if(!h && dev) { r=(*dev)->ObtainExclusiveAccess(dev); printf("exclusive 0x%08x\n",r); if(!r)(*dev)->ReleaseExclusiveAccess(dev); (*dev)->Release(dev); }
   IODestroyPlugInInterface(plug);
  }
  IOObjectRelease(s);
 }
 IOObjectRelease(it); return 0;
}
