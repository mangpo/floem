////////////////////////////////////////////////////////////////////////////////
//
// tdes.c - Easy Triple-DES
// Copyright (C) 2009  Mehter Tariq <mehtertariq@integramicro.com>
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program.  If not, see <http://www.gnu.org/licenses/>.
//
////////////////////////////////////////////////////////////////////////////////

#include <stdio.h>

#define _TDES_H_
#include "tdes.h"

void left_shift(int n, unsigned char *arr) {
	int i, j;
	for (i=0; i<n; i++) {
		temp=*(arr+0);
		for (j=0; j<28; j++) {
			*(arr+j)=*(arr+j+1);
		}
		*(arr+27)=temp;
	}
}
void print(unsigned char arr[]) {
	int i;
	for (i=0; i<64; i++) {
		printf("%4d", arr[i]);
		if ((i+1)%8==0) {
			printf("\n");
		}
	}
	printf("\n");
}
void tdes_init(unsigned char key_ring[3][8]) {
	int stage;
	int i, j;
	for (stage=0; stage<3; stage++) {
		for (i=0; i<8; i++) {
			for (j=0; j<8; j++) {
				key[stage][i*8+j]=(key_ring[stage][i]&(0x01<<(7-j)))>>(7-j);
			}
		}
	}
	for (stage=0; stage<3; stage++) {
		for (i=0; i<28; i++) {
			c[i]=key[stage][pc1[i]-1];
			d[i]=key[stage][pc1[i+28]-1];
		}
		for (i=0; i<16; i++) {
			left_shift(left_shifts[i], c);
			left_shift(left_shifts[i], d);
			for (j=0; j<28; j++) {
				cd[j]=c[j];
				cd[j+28]=d[j];
			}
			for (j=0; j<48; j++) {
				k[stage][i][j]=cd[pc2[j]-1];
			}
		}
	}
}
void des_encrypt(int stage) {
	int i, j;
	for (i=0; i<64; i++) {
		et[i]=pt[i];
	}
	for (i=0; i<64; i++) {
		perm_input[i]=et[ip[i]-1];
	}
	for (i=0; i<32; i++) {
		l[i]=perm_input[i];
		r[i]=perm_input[i+32];
	}
	for (i=0; i<16; i++) {
		for (j=0; j<48; j++) {
			b[j]=r[e[j]-1]^k[stage-1][i][j];
		}
		for (j=0; j<8; j++) {
			row=(b[j*6+0]<<1)|(b[j*6+5]);
			col=(b[j*6+1]<<3)|(b[j*6+2]<<2)|(b[j*6+3]<<1)|b[j*6+4];
			switch (j) {
			case 0:
				s_element=s1[row][col];
				break;
			case 1:
				s_element=s2[row][col];
				break;
			case 2:
				s_element=s3[row][col];
				break;
			case 3:
				s_element=s4[row][col];
				break;
			case 4:
				s_element=s5[row][col];
				break;
			case 5:
				s_element=s6[row][col];
				break;
			case 6:
				s_element=s7[row][col];
				break;
			case 7:
				s_element=s8[row][col];
				break;
			default:
				break;
			}
			s[j*4+0]=(s_element&0x08)>>3;
			s[j*4+1]=(s_element&0x04)>>2;
			s[j*4+2]=(s_element&0x02)>>1;
			s[j*4+3]=s_element&0x01;
		}
		for (j=0; j<32; j++) {
			f[j]=s[p[j]-1];
		}
		for (j=0; j<32; j++) {
			temp=r[j];
			r[j]=l[j]^f[j];
			l[j]=temp;
		}
	}
	for (i=0; i<32; i++) {
		pre_output[i]=r[i];
		pre_output[i+32]=l[i];
	}
	for (i=0; i<64; i++) {
		et[i]=pre_output[ip_inv[i]-1];
	}
}
void des_decrypt(int stage) {
	int i, j;
	for (i=0; i<64; i++) {
		pt[i]=et[i];
	}
	for (i=0; i<64; i++) {
		perm_input[i]=pt[ip[i]-1];
	}
	for (i=0; i<32; i++) {
		r[i]=perm_input[i];
		l[i]=perm_input[i+32];
	}
	for (i=16; i>0; i--) {
		for (j=0; j<48; j++) {
			b[j]=l[e[j]-1]^k[stage-1][i-1][j];
		}
		for (j=0; j<8; j++) {
			row=(b[j*6+0]<<1)|(b[j*6+5]);
			col=(b[j*6+1]<<3)|(b[j*6+2]<<2)|(b[j*6+3]<<1)|b[j*6+4];
			switch (j) {
			case 0:
				s_element=s1[row][col];
				break;
			case 1:
				s_element=s2[row][col];
				break;
			case 2:
				s_element=s3[row][col];
				break;
			case 3:
				s_element=s4[row][col];
				break;
			case 4:
				s_element=s5[row][col];
				break;
			case 5:
				s_element=s6[row][col];
				break;
			case 6:
				s_element=s7[row][col];
				break;
			case 7:
				s_element=s8[row][col];
				break;
			default:
				break;
			}
			s[j*4+0]=(s_element&0x08)>>3;
			s[j*4+1]=(s_element&0x04)>>2;
			s[j*4+2]=(s_element&0x02)>>1;
			s[j*4+3]=s_element&0x01;
		}
		for (j=0; j<32; j++) {
			f[j]=s[p[j]-1];
		}
		for (j=0; j<32; j++) {
			temp=l[j];
			l[j]=r[j]^f[j];
			r[j]=temp;
		}
	}
	for (i=0; i<32; i++) {
		pre_output[i]=l[i];
		pre_output[i+32]=r[i];
	}
	for (i=0; i<64; i++) {
		pt[i]=pre_output[ip_inv[i]-1];
	}
}
void tdes_encrypt(unsigned long n, unsigned char *in, unsigned char *out) {
	unsigned long i, j, k, cnt;
	cnt=n;
	if ((n%8)!=0) {
		for (cnt=n; cnt<8*(n/8)+8; cnt++) {
			*(in+cnt)=0x00;
		}
	}
	for (i=0; i<cnt; i+=8) {
		for (j=0; j<8; j++) {
			for (k=0; k<8; k++) {
				pt[j*8+k]=((*(in+i+j))&(0x01<<(7-k)))>>(7-k);
			}
		}
		//printf("\nTDES Ciphertext Block %d:\n", i/8);
		des_encrypt(1);
		des_decrypt(2);
		des_encrypt(3);
		for (j=0; j<8; j++) {
			*(out+i+j)=0x00;
			for (k=0; k<8; k++) {
				if (et[j*8+k]==0x01) {
					*(out+i+j)|=(0x01<<(7-k));
				}
				else {
					*(out+i+j)&=~(0x01<<(7-k));
				}
			}
		}
		/* for (j=i; j<i+8; j++) { */
		/* 	printf("%2x ", *(out+j)); */
		/* } */
		//getchar();
	}
	//printf("\n\n");
}
void tdes_decrypt(unsigned long n, unsigned char *in, unsigned char *out) {
	unsigned long i, j, k, cnt;
	cnt=n;
	if ((n%8)!=0) {
		cnt=8*(n/8)+8;
	}
	for (i=0; i<cnt; i+=8) {
		for (j=0; j<8; j++) {
			for (k=0; k<8; k++) {
				et[j*8+k]=((*(in+i+j))&(0x01<<(7-k)))>>(7-k);
			}
		}
		//printf("\nTDES Plaintext Block %d:\n", i/8);
		des_decrypt(3);
		des_encrypt(2);
		des_decrypt(1);
		for (j=0; j<8; j++) {
			*(out+i+j)=0x00;
			for (k=0; k<8; k++) {
				if (pt[j*8+k]==0x01) {
					*(out+i+j)|=(0x01<<(7-k));
				}
				else {
					*(out+i+j)&=~(0x01<<(7-k));
				}
			}
		}
		/* for (j=i; j<i+8; j++) { */
		/* 	printf("%2x ", *(out+j)); */
		/* } */
		//getchar();
	}
	//printf("\n\n");
}
