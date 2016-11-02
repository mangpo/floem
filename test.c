#include<stdio.h>
#include<stdlib.h>

struct datapacket {
  int size;
  int data[];
};

int main() {

  struct datapacket *pkt =
    malloc( sizeof(struct datapacket) +
            sizeof(int)*10 );
  pkt->size = 10;
  pkt->data[5] = 55;
  printf("%d %d\n", pkt->size, pkt->data[5]);
  return 0;
}
