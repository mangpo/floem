#include "tmp_spec.h"

void run_app() {
  eq_entry* e = get_eq();
  if(e == NULL) {
    printf("eq_entry is null.\n");
  } else {
    printf("eq_entry: %ld %d\n", e->opaque, e->keylen);
    item *it = hasht_get(e->key, e->keylen, e->hash);
    cq_entry* c = (cq_entry *) malloc(sizeof(cq_entry));
    c->it = it;
    c->opaque = e->opaque;
    send_cq(c);
  }
}

int main() {
  populate_hasht(64);
  init();
  run_threads();

  usleep(1000);
  for(int i=0;i<10;i++) {
    run_app();
    usleep(1000);
  }

  usleep(10000);

  kill_threads();
  return 0;
}
