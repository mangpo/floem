#include <stdio.h>
#include <stdlib.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <netinet/in.h>
#include <arpa/inet.h> 
#include <assert.h>
#include <stdint.h>
#include <string.h>

#define N 4

#define MAX(x,y) (x>y)? x: y;

struct tuple {
  volatile int		task, fromtask;
  uint64_t 	starttime;
  struct {
    char	str[64];
    int		integer;
  } v[5];
};

void server() {
  uint16_t		port = 7001;
  int listener = 0;
  struct sockaddr_in serv_addr; 

  char sendBuff[1025];
  time_t ticks;

  printf("server starts...\n");

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
  assert(r == 0);
  printf("bind\n");

  r = listen(listener, 4);
  assert(r == 0);
  printf("listen\n");

  fd_set readfds;
  
  int channel = 0;
  // Do we have a new connection? Accept it!
  printf("here %d\n", FD_ISSET(listener, &readfds));
  //if(FD_ISSET(listener, &readfds)) {
    channel = accept(listener, NULL, NULL);
    assert(channel != -1);
    printf("accept connection\n");
    FD_CLR(listener, &readfds);
    //  }
  printf("here %d\n", FD_ISSET(listener, &readfds));

  int nfds = MAX(listener, channel);
  FD_ZERO(&readfds);
  //FD_SET(listener, &readfds);
  FD_SET(channel, &readfds);
  r = select(nfds + 1, &readfds, NULL, NULL, NULL);
  
  size_t rest = 0;
  struct tuple data[N];
  while(rest < N) {
    //printf("wait...\n");
    if(FD_ISSET(channel, &readfds)) {
      char *bufp = ((char *) &data) + rest;
      ssize_t ret = recv(channel, bufp, N * sizeof(struct tuple), 0);
      assert(ret != -1);
      rest += ret;
      printf("recv %ld bytes\n", ret);
      }
  }

  for(int i=0; i<N; i++) {
    printf("tuple[%d]: v[0].str = %s, v[0].integer = %d\n", i, data[i].v[0].str, data[i].v[0].integer);
  }

}

void client() {

  printf("client starts...\n");

  const char		*hostname = "127.0.0.1";
  uint16_t		port = 7001;
  struct sockaddr_in saddr = {
    .sin_family = AF_INET,
    .sin_port = htons(port),
  };
  int sock = socket(AF_INET, SOCK_STREAM, 0);
  assert(sock != -1);

  int r = inet_pton(AF_INET, hostname, &saddr.sin_addr);
  assert(r == 1);

  r = connect(sock, (void *)&saddr, sizeof(struct sockaddr_in));
  assert(r == 0);

  struct tuple data[N];
  strcpy(data[0].v[0].str, "mangpo");
  strcpy(data[1].v[0].str, "maprang");
  strcpy(data[2].v[0].str, "hua");
  strcpy(data[3].v[0].str, "pom");
  for(int i=0; i<N; i++) {
    data[i].v[0].integer = i;
    send(sock, &data[i], sizeof(struct tuple), 0);
    printf("send %d\n", i);
  }
}

int main(int argc, char *argv[]) {
  assert(argc > 1);
  int workerid = atoi(argv[1]);
  printf("worder %d\n", workerid);

  if(workerid == 0) server();
  else client();
  
}
