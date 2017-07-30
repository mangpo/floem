#ifndef SHM_H
#define SHM_H

#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <sys/types.h>
#include <unistd.h>
#include <sys/stat.h>
#include <sys/mman.h>
#include <fcntl.h>
#include <errno.h>
#include <linux_hugepage.h>

/* create and map a shared memory region, returns address */
static void *util_create_shmsiszed(const char *name, size_t size)
{
  int fd;
  void *p;

  if ((fd = shm_open(name, O_CREAT | O_RDWR, 0666)) == -1) {
    perror("shm_open failed");
    goto error_out;
  }
  if (ftruncate(fd, size) != 0) {
    perror("ftruncate failed");
    goto error_remove;
  }

  if ((p = mmap(NULL, size, PROT_READ | PROT_WRITE,
      MAP_SHARED | MAP_POPULATE, fd, 0)) == (void *) -1)
  {
    perror("mmap failed");
    goto error_remove;
  }

  memset(p, 0, size);

  close(fd);
  return p;

error_remove:
  close(fd);
  shm_unlink(name);
error_out:
  return NULL;
}

/* map a shared memory region, returns address */
static void *util_map_shm(const char *name, size_t size)
{
  int fd;
  void *p;

  if ((fd = shm_open(name, O_RDWR, 0666)) == -1) {
    perror("shm_open failed");
    return NULL;
  }

  p = mmap(NULL, size, PROT_READ | PROT_WRITE, MAP_SHARED | MAP_POPULATE,
      fd, 0);
  close(fd);
  if (p == (void *) -1) {
    perror("mmap failed");
    return NULL;
  }

  return p;
}

static void* util_map_dma() {
    void* virt;
    uint64_t phys;
    size_t size;
    bool s;
    s = huge_alloc_phys(&virt, &phys, &size);
    if(!s) exit(1);
    printf("physical address = %p, size = %ld\n", (void*) phys, size);
    printf("logical address = %p\n", virt);
    return virt;
}

/*
#define UIO_DEV "/dev/uio0"  
#define UIO_ADDR "/sys/class/uio/uio0/maps/map0/addr"  
#define UIO_SIZE "/sys/class/uio/uio0/maps/map0/size"  

static char uio_addr_buf[16], uio_size_buf[16];  
static int uio_fd, addr_fd, size_fd;

static void* util_map_dma()  
{  
    int i;  
    int uio_size;  
    void* uio_addr, *access_address;  

    uio_fd = open(UIO_DEV, O_RDWR);
    addr_fd = open(UIO_ADDR, O_RDONLY);  
    size_fd = open(UIO_SIZE, O_RDONLY);  
    if( addr_fd < 0 || size_fd < 0 || uio_fd < 0) {  
        fprintf(stderr, "mmap: %s\n", strerror(errno));  
        exit(-1);  
    }  
    read(addr_fd, uio_addr_buf, sizeof(uio_addr_buf));  
    read(size_fd, uio_size_buf, sizeof(uio_size_buf));  
    uio_addr = (void*)strtoul(uio_addr_buf, NULL, 0);  
    uio_size = (int)strtol(uio_size_buf, NULL, 0);  

    access_address = mmap(NULL, uio_size, PROT_READ | PROT_WRITE,  
            MAP_SHARED, uio_fd, 0);  
    if ( access_address == (void*) -1) {  
        fprintf(stderr, "mmap: %s\n", strerror(errno));  
        exit(-1);  
    }  
    printf("The device address %p (lenth %d)\n"  
            "can be accessed over\n"  
            "logical address %p\n", uio_addr, uio_size, access_address);

    return access_address;
}

static void util_unmap_dma() {
    close(uio_fd);
    close(addr_fd);
    close(size_fd);
}
*/


#endif
