#ifndef SOCKET_H
#define SOCKET_H

#include <sys/socket.h>
#include <sys/types.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <assert.h>

static int create_server_socket(uint16_t port) {
  int listener = 0;
  struct sockaddr_in serv_addr;

  printf("create socket\n");
  listener = socket(AF_INET, SOCK_STREAM, 0);
  assert(listener != -1);

  int optval = 1;
  int r = setsockopt(listener, SOL_SOCKET, SO_REUSEADDR, &optval, sizeof(int));
  assert(r == 0);

  struct sockaddr_in saddr = {
    .sin_family = AF_INET,
    .sin_port = htons(port),
    .sin_addr = { INADDR_ANY },
  };

  r = bind(listener, (void *)&saddr, sizeof(saddr));
  if(r != 0)
    printf("bind failed with status %d.\n", r);
  assert(r == 0);

  r = listen(listener, 4); // backlog
  printf("socket listen\n");

  return listener;
}

static int create_client_socket() {
  printf("client starts...\n");
  int sock = socket(AF_INET, SOCK_STREAM, 0);
  assert(sock != -1);

  return sock;
}

static struct sockaddr_in create_sockaddr(const char* hostname, uint16_t port) {
  struct sockaddr_in saddr = {
    .sin_family = AF_INET,
    .sin_port = htons(port),
  };

  if(hostname != NULL) {
    int r = inet_pton(AF_INET, hostname, &saddr.sin_addr);
    assert(r == 1);
  }

  return saddr;
}

#endif