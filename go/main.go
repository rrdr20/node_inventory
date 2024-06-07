/*
Reads SMBIOS information based on version 3.2.0 from the DMTF published on 04/26/2018.
Link: https://www.dmtf.org/sites/default/files/standards/documents/DSP0134_3.2.0.pdf

version 0.0
*/

package main

import (
	"bufio"
	"bytes"
	"encoding/binary"
	"errors"
	"fmt"
	"io"
	"os"
)

const (
	sysfsEntrypoint = "/sys/firmware/dmi/tables/smbios_entry_point"
	sysfsDMI        = "/sys/firmware/dmi/tables/DMI"
	headerLen       = 4
)

var (
	anchor             = []byte("_SM_")
	intermediateAnchor = []byte("_DMI_")
	terminater         = []byte{0x00, 0x00}
)

type EntryPoint struct {
	Anchor                string // Anchor string (_SM_)
	IntermediateAnchor    string // size of 5 (_DMI_)
	Checksum              uint8
	Length                uint8
	Major                 uint8
	Minor                 uint8
	MaxStructureSize      uint16
	EntryPointRevision    uint8   // if this value is 0 then next 5 bytes are set to 0
	FormattedArea         [5]byte // set to 0 if EntryPointRevision is set to 0
	IntermediateChecksum  uint8
	StructureTableLength  uint16
	StructureTableAddress uint32
	NumberStructures      uint16
	BCDRevision           uint8
}

type Header struct {
	Type   uint8
	Length uint8
	Handle uint16
}

type Structure struct {
	Formatterd []byte
	Strings    []string
	Header     Header
}

type SmTable struct {
	Structures []Structure
}

func main() {
	// If the files do not exist do not proceed, exit with error
	_, err := os.Stat(sysfsEntrypoint)
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}

	_, err = os.Stat(sysfsDMI)
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}

	// If the file cannot be opened do not proceed, exit with error
	smbepf, err := os.Open(sysfsEntrypoint)
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	defer smbepf.Close()

	// Parse and return EntryPoint info
	ep, err := parseSmbEntryPoint(smbepf)
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}

	dmiTablef, err := os.Open(sysfsDMI)
	if err != nil {
		fmt.Println(err)
		os.Exit(1)
	}
	defer dmiTablef.Close()

	parseDmiTable(dmiTablef)

	fmt.Println(*ep)
}

func parseSmbEntryPoint(smbepf io.Reader) (*EntryPoint, error) {
	// Location index of the checksum byte
	const chksumIdx int = 4

	b, err := io.ReadAll(smbepf)
	if err != nil {
		return nil, err
	}

	// If the Anchor is not present then no need to proceed, return error
	if !bytes.HasPrefix(b, anchor) {
		return nil, errors.New("SMBIOS anchor not found")
	}

	// Caclulate the checksum
	if err := checksum(b[chksumIdx], chksumIdx, b); err != nil {
		return nil, err
	}

	ep := EntryPoint{
		// First 4 bytes is the anchor
		Anchor:                string(b[0:4]),
		Checksum:              b[4],
		Length:                b[5],
		Major:                 b[6],
		Minor:                 b[7],
		MaxStructureSize:      binary.LittleEndian.Uint16(b[8:10]),
		EntryPointRevision:    b[10],
		IntermediateAnchor:    string(b[16:21]),
		IntermediateChecksum:  b[21],
		StructureTableLength:  binary.LittleEndian.Uint16(b[22:24]),
		StructureTableAddress: binary.LittleEndian.Uint32(b[24:28]),
		NumberStructures:      binary.LittleEndian.Uint16(b[28:30]),
		BCDRevision:           b[30],
	}
	copy(ep.FormattedArea[:], b[11:16])

	return &ep, nil
}

func parseDmiTable(dmiTablef io.ReadCloser) error {
	br := bufio.NewReader(dmiTablef)

	for {
		buf := make([]byte, headerLen)
		if _, err := io.ReadFull(br, buf); err != nil {
			break
		}

		h := Header{
			Type:   buf[0],
			Length: buf[1],
			Handle: binary.LittleEndian.Uint16(buf[2:4]),
		}

		length := h.Length - headerLen

		buf = make([]byte, length)
		if _, err := io.ReadFull(br, buf); err != nil {
			return errors.New("unable to read dmi data")
		}

		s := Structure{
			Header:     h,
			Formatterd: buf,
			Strings:    []string{},
		}

		for {
			term, err := br.Peek(2)
			if err != nil {
				return errors.New("unable to read dmi data")
			}

			if bytes.Equal(term, terminater) {
				br.Discard(2)
				break
			} else {
				raw, err := br.ReadBytes(0x00)
				if err != nil {
					return errors.New("read err parsing string")
				}
				ss := bytes.TrimRight(raw, "\x00")
				s.Strings = append(s.Strings, string(ss))
				peek, err := br.Peek(1)
				if err != nil {
					return errors.New("unable to read dmi data")
				}
				if bytes.Equal(peek, []byte{0x00}) {
					br.Discard(1)
					break
				}
			}
		}

		fmt.Printf("%+v\n", s)
	}

	return nil
}

func checksum(checksum uint8, idx int, b []byte) error {
	chk := checksum
	for i := range b {
		if i == idx {
			continue
		}
		chk += b[i]
	}

	if chk != 0 {
		return errors.New("Invalid checksum")
	}

	return nil
}
