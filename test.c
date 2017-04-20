#include<stdio.h>
#include<stdlib.h>

typedef struct _abc { 
  int a; int b; int c[10];
} abc;

int main() {
  abc* x = (abc *) malloc(sizeof(abc));
  for(int i=0; i<10; i++) {
    printf("%d\n", x->c[i]);
  }
  return 0;
}
