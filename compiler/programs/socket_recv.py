from dsl import *

Item = create_state("item", "int x; int y;")
Stream = create_state("stream", r'''
    int listener;
    int channel[MAX_WORKERS];
    item inbuf[MAX_WORKERS][MAX_INBUF];
    int rest[MAX_WORKERS];
    int nchannels;
    int active;''')
s = Stream(init=["create_server_socket(7001)", 0, [0], 0, 0, 0])

FROM_NET_SAVE = create_element("FROM_NET_SAVE", [], [Port("out", [])], r'''
    fd_set readfds;
    int nfds = this->listener;
    FD_ZERO(&readfds);
    FD_SET(this->listener, &readfds);
    for(int i = 0; i < this->nchannels; i++) {
        FD_SET(this->channel[i], &readfds);
        nfds = (this->channel[i] > nfds)? this->channel[i]: nfds;
    }
    int r = select(nfds + 1, &readfds, NULL, NULL, NULL);

    if(FD_ISSET(this->listener, &readfds)) {
        int channel = accept(this->listener, NULL, NULL);
        assert(channel != -1);
        this->channel[this->nchannels] = channel;
        this->nchannels++;
        printf("new connection!\n");
    }

    int active = this->active + 1; // round robin
    for(int k = 0; k < this->nchannels; k++) {
        int i = (k + active) % this->nchannels;
        int channel = this->channel[i];
        if(FD_ISSET(channel, &readfds)) {
            if(this->rest[i] >= sizeof(item)) {
                int newrest = this->rest[i] % sizeof(item);
                memmove(this->inbuf[i], &this->inbuf[i][this->rest[i] / sizeof(item)], newrest);
                this->rest[i] = newrest;
            }
            char *bufp = ((char *) this->inbuf[i]) + this->rest[i];
            ssize_t ret = recv(channel, bufp, MAX_INBUF * sizeof(item) - this->rest[i], 0);
            assert(ret != -1);
            this->rest[i] += ret;
            this->active = i;
            printf("channel %d: receive %ld bytes\n", i, ret);
            break;
        }
    }

    output { out(); }
            ''', [("stream", "this")])
from_net_save = FROM_NET_SAVE("from_net_save", [s])

FROM_NET_READ = create_element("FROM_NET_READ", [Port("in", [])], [Port("out", ["item*"])], r'''
    int i = this->active;
    for(int k = 0; k < this->rest[i] / sizeof(item); k++) {
        item *t = &this->inbuf[i][k];
        out(t);
        //printf("item %d %d\n", t->x, t->y);
    }
    output multiple;
            ''', [("stream", "this")])
from_net_read = FROM_NET_READ("from_net_read", [s])

display = create_element_instance("display", [Port("in", ["item*"])], [],
                                  r'''
    (item* t) = in();
    printf("item %d %d\n", t->x, t->y);
                                  ''')

##########################
Sock = create_state("Sock", r'''
    int sock;
    struct sockaddr_in saddr;
    bool connected;''')
sock = Sock(init=['create_client_socket()', 'create_sockaddr("127.0.0.1", 7001)', False])

TO_NET_SEND = create_element("TO_NET_SEND", [Port("in", ["item*"])], [], r'''
    (item* t) = in();
    if(!this->connected) {
        printf("client try to connect.\n");
        int r = connect(this->sock, (void *)&this->saddr, sizeof(struct sockaddr_in));
        assert(r == 0);
        printf("client connects.\n");
        this->connected = true;
    }
    send(this->sock, t, sizeof(item), 0);
    printf("send %d\n", t->x);
            ''', [("Sock", "this")])
to_net_send = TO_NET_SEND("to_net_send", [sock])


@internal_trigger("print_item")
def print_item():
    display(from_net_read(from_net_save()))

@API("send_item")
def send_item(t):
    to_net_send(t)


c = Compiler()
c.include = r'''
#include <sys/socket.h>
#include <sys/types.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <assert.h>

#define MAX_WORKERS 2
#define MAX_INBUF	8192

int create_server_socket(uint16_t port) {
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
  assert(r == 0);

  r = listen(listener, 4); // backlog
  printf("socket listen\n");

  return listener;
}

int create_client_socket() {
  printf("client starts...\n");
  int sock = socket(AF_INET, SOCK_STREAM, 0);
  assert(sock != -1);

  return sock;
}

struct sockaddr_in create_sockaddr(const char* hostname, uint16_t port) {
  struct sockaddr_in saddr = {
    .sin_family = AF_INET,
    .sin_port = htons(port),
  };

  int r = inet_pton(AF_INET, hostname, &saddr.sin_addr);
  assert(r == 1);

  return saddr;
}
'''

c.testing = r'''
  item data[4];
  for(int i=0; i<4; i++) {
    data[i].x = i;
    data[i].y = 100 + i;
    send_item(&data[i]);
  }
'''
c.generate_code_and_run()