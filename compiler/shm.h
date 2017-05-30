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


#endif