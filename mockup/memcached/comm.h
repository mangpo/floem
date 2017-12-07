/* App doorbell */
struct flextcp_pl_adb {
  union {
    struct {
      uint32_t rx_tail;
      uint32_t tx_tail;
    } bumpqueue;
    uint8_t raw[62];
  } __attribute__((packed)) msg;
  uint8_t type;
  volatile uint8_t nic_own;
} __attribute__((packed));

/** Kernel doorbell format */
struct flextcp_pl_kdb {
  union {
    struct {
      uint64_t rx_base;
      uint64_t tx_base;
      uint32_t rx_len;
      uint32_t tx_len;
    } setqueue;
    struct {
      uint32_t rx_tail;
      uint32_t tx_tail;
    } bumpqueue;
  } msg;
  uint8_t _pad[36];
  uint16_t flags;
  uint8_t _pad1;
  volatile uint8_t nic_own;
} __attribute__((packed));
