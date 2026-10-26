#import <Foundation/Foundation.h>
#import <IOKit/IOKitLib.h>
#import <IOUSBHost/IOUSBHost.h>
#include <unistd.h>
static IOUSBHostDevice *device;
static IOUSBHostInterface *interface;
static IOUSBHostPipe *input,*output;
static char errorText[1024];
const char *gb_error(void) { return errorText; }
static int fail(NSString *stage,NSError *error) { snprintf(errorText,sizeof(errorText),"%s: %s",stage.UTF8String,error.description.UTF8String);return -1; }
void gb_close(void) { @autoreleasepool { input=nil;output=nil;[interface destroy];interface=nil;[device destroy];device=nil; } }
int gb_open(void) { @autoreleasepool {
 CFMutableDictionaryRef match=[IOUSBHostDevice createMatchingDictionaryWithVendorID:@0x4c4a productID:@0x3442 bcdDevice:nil deviceClass:nil deviceSubclass:nil deviceProtocol:nil speed:nil productIDArray:nil];
 io_service_t svc=IOServiceGetMatchingService(kIOMainPortDefault,match);
 if(!svc) return -2;
 NSError *error=nil;
 device=[[IOUSBHostDevice alloc] initWithIOService:svc options:IOUSBHostObjectInitOptionsDeviceCapture queue:nil error:&error interestHandler:nil];
 IOObjectRelease(svc);
 if(!device) return fail(@"Capture",error);
 if(![device configureWithValue:1 matchInterfaces:NO error:&error]) { int r=fail(@"Configure",error);gb_close();return r; }
 for(int attempt=0;attempt<50 && !interface;attempt++) {
  io_iterator_t iter=0;
  IORegistryEntryCreateIterator(device.ioService,kIOServicePlane,kIORegistryIterateRecursively,&iter);
  io_service_t child;
  while((child=IOIteratorNext(iter))) {
   if(IOObjectConformsTo(child,"IOUSBHostInterface")) {
    interface=[[IOUSBHostInterface alloc] initWithIOService:child options:0 queue:nil error:&error interestHandler:nil];
    IOObjectRelease(child);break;
   }
   IOObjectRelease(child);
  }
  IOObjectRelease(iter);
  if(!interface) usleep(20000);
 }
 if(!interface) { int r=fail(@"Open interface",error);gb_close();return r; }
 input=[interface copyPipeWithAddress:0x81 error:&error];
 output=[interface copyPipeWithAddress:0x01 error:&error];
 if(!input || !output) { int r=fail(@"Open pipes",error);gb_close();return r; }
 return 0;
} }
int gb_transfer(int endpoint,void *buffer,int length,int timeoutMs) { @autoreleasepool {
 if(length<0 || length>65535 || (endpoint!=1 && endpoint!=0x81)) return -1;
 NSMutableData *data=[NSMutableData dataWithLength:length];
 if(endpoint==1) memcpy(data.mutableBytes,buffer,length);
 NSUInteger count=0; NSError *error=nil;
 BOOL ok=[(endpoint==1?output:input) sendIORequestWithData:data bytesTransferred:&count completionTimeout:timeoutMs/1000.0 error:&error];
 if(!ok) return fail(@"Bulk transfer",error);
 if(count>(NSUInteger)length) return -1;
 if(endpoint==0x81) memcpy(buffer,data.bytes,count);
 return (int)count;
} }
