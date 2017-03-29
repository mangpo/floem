#include<stdio.h>
#include<stdlib.h>

int* p;

int main() {
  p = malloc(sizeof(int)* 10);
  printf("%d %d\n", p[0], sizeof(int));
  return 0;
}
