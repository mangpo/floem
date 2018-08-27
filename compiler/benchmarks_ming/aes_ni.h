#ifndef _AES_NI_H_
#define _AES_NI_H_

#include "aes_ni.h"

void aes128_load_key(int8_t *enc_key);
void aes128_enc(int8_t *plainText,int8_t *cipherText);
void aes128_dec(int8_t *cipherText,int8_t *plainText);

#endif
