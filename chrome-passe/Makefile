# Chrome Passe — native macOS launcher
#
# Build:   make
# Install: make install
# Clean:   make clean

BINARY   = chrome-passe
SOURCE   = handler.swift
APP_DIR  = $(HOME)/Applications/Chrome Passe.app

SWIFTC     = swiftc
FRAMEWORKS = -framework Cocoa
SWIFT_FLAGS = -O $(FRAMEWORKS)

.PHONY: all install clean

all: $(BINARY)

$(BINARY): $(SOURCE)
	$(SWIFTC) $(SWIFT_FLAGS) -target arm64-apple-macosx12.0 -o $(BINARY)-arm64 $<
	$(SWIFTC) $(SWIFT_FLAGS) -target x86_64-apple-macosx12.0 -o $(BINARY)-x86_64 $<
	lipo -create -output $@ $(BINARY)-arm64 $(BINARY)-x86_64
	rm $(BINARY)-arm64 $(BINARY)-x86_64
	codesign -s - $@

install: $(BINARY)
	./install.sh

clean:
	rm -f $(BINARY) $(BINARY)-arm64 $(BINARY)-x86_64
