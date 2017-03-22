#include<stdio.h>
#include<stdlib.h>

typedef struct {
    int flags;
    //uint16_t len;
} __attribute__((packed)) cq_entry;

int main() {
  printf("hello\n");
  return 0;
}
