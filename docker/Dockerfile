# SH-2 (CPS3) cross toolchain: binutils + GCC (C only, libgcc) for sh-elf, big-endian SH-2, no newlib.
#   docker build -t cps3-dev:latest docker
FROM ubuntu:24.04
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential wget xz-utils ca-certificates libgmp-dev libmpfr-dev libmpc-dev texinfo \
      make python3 python3-pil \
 && rm -rf /var/lib/apt/lists/*
ARG BU=2.42
ARG GCC=13.3.0
WORKDIR /src
RUN wget -q https://ftp.gnu.org/gnu/binutils/binutils-$BU.tar.xz && tar xf binutils-$BU.tar.xz \
 && mkdir b && cd b && ../binutils-$BU/configure --target=sh-elf --prefix=/opt/sh --disable-nls --disable-werror \
 && make -j$(nproc) && make install && cd .. && rm -rf b binutils-$BU*
ENV PATH=/opt/sh/bin:$PATH
RUN wget -q https://ftp.gnu.org/gnu/gcc/gcc-$GCC/gcc-$GCC.tar.xz && tar xf gcc-$GCC.tar.xz \
 && mkdir g && cd g && ../gcc-$GCC/configure --target=sh-elf --prefix=/opt/sh --enable-languages=c \
      --with-cpu=m2 --disable-multilib --without-headers --with-newlib --disable-nls --disable-shared \
      --disable-threads --disable-lto --disable-libssp --disable-libquadmath --disable-libgomp --disable-libatomic \
 && make -j$(nproc) CFLAGS=-O2 CXXFLAGS=-O2 all-gcc all-target-libgcc && make install-gcc install-target-libgcc \
 && cd .. && rm -rf g gcc-$GCC*
WORKDIR /p
# numpy for tools/stest_check.py
RUN apt-get update && apt-get install -y --no-install-recommends python3-numpy && rm -rf /var/lib/apt/lists/*
