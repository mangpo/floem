// gcc -O3 shm_test.c -o shm_test -lrt
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

#define SHM_SIZE (1024 * 64)
#define SHM_NAME "/myshm"

/* create and map a shared memory region, returns address */
void *util_create_shmsiszed(const char *name, size_t size)
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
void *util_map_shm(const char *name, size_t size)
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

static int server_main(void)
{
  void *shm;
  volatile uint8_t *p;

  if ((shm = util_create_shmsiszed(SHM_NAME, SHM_SIZE)) == NULL) {
    fprintf(stderr, "creating shared memory failed\n");
    return EXIT_FAILURE;
  }
  printf("Shared memory created\n");
  p = (volatile uint8_t *) shm;

  printf("Writing for client to write value\n");
  while (*p == 0);
  printf("Client wrote %u\n", *p);

  /* unlink can be done before unmap, memory is still available but can no
   * longer be mapped */
  if (shm_unlink(SHM_NAME) != 0) {
    perror("Deleting shared memory failed");
    return EXIT_FAILURE;
  }
  printf("Shared memory deleted\n");

  if (munmap(shm, SHM_SIZE) != 0) {
    perror("Unmapping shared memory failed");
    return EXIT_FAILURE;
  }
  printf("Shared memory unmapped\n");

  return EXIT_SUCCESS;
}

static int client_main(void)
{
  void *shm;
  volatile uint8_t *p;

  if ((shm = util_map_shm(SHM_NAME, SHM_SIZE)) == NULL) {
    fprintf(stderr, "mapping shared memory failed\n");
    return EXIT_FAILURE;
  }
  printf("Shared memory mapped\n");
  p = (volatile uint8_t *) shm;

  if (*p != 0) {
    fprintf(stderr, "Shared memory not zeroed\n");
    return EXIT_FAILURE;
  }

  printf("Writing value 42\n");
  *p = 42;
  printf("Wrote value\n");

  if (munmap(shm, SHM_SIZE) != 0) {
    perror("Unmapping shared memory failed");
    return EXIT_FAILURE;
  }
  printf("Shared memory unmapped\n");

  return EXIT_SUCCESS;
}

int main(int argc, char *argv[])
{
  if (argc == 2 && !strcmp(argv[1], "server")) {
    return server_main();
  } else if (argc == 2 && !strcmp(argv[1], "client")) {
    return client_main();
  } else {
    fprintf(stderr, "Usage: shm_test SERVER | shm_test CLIENT\n");
    return EXIT_FAILURE;
  }
}
