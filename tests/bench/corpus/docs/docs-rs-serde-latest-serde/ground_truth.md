## Expand description

[§](https://docs.rs#serde)Serde

Serde is a framework for * ser*ializing and

*serializing Rust data structures efficiently and generically.*

**de**The Serde ecosystem consists of data structures that know how to serialize and deserialize themselves along with data formats that know how to serialize and deserialize other things. Serde provides the layer by which these two groups interact with each other, allowing any supported data structure to be serialized and deserialized using any supported data format.

See the Serde website [https://serde.rs](https://serde.rs) for additional documentation and
usage examples.

[§](https://docs.rs#design)Design

Where many other languages rely on runtime reflection for serializing data,
Serde is instead built on Rust’s powerful trait system. A data structure
that knows how to serialize and deserialize itself is one that implements
Serde’s `Serialize`

and `Deserialize`

traits (or uses Serde’s derive
attribute to automatically generate implementations at compile time). This
avoids any overhead of reflection or runtime type information. In fact in
many situations the interaction between data structure and data format can
be completely optimized away by the Rust compiler, leaving Serde
serialization to perform the same speed as a handwritten serializer for the
specific selection of data structure and data format.

[§](https://docs.rs#data-formats)Data formats

The following is a partial list of data formats that have been implemented for Serde by the community.

[JSON](https://github.com/serde-rs/json), the ubiquitous JavaScript Object Notation used by many HTTP APIs.[Postcard](https://github.com/jamesmunns/postcard), a no_std and embedded-systems friendly compact binary format.[CBOR](https://github.com/enarx/ciborium), a Concise Binary Object Representation designed for small message size without the need for version negotiation.[YAML](https://github.com/dtolnay/serde-yaml), a self-proclaimed human-friendly configuration language that ain’t markup language.[MessagePack](https://github.com/3Hren/msgpack-rust), an efficient binary format that resembles a compact JSON.[TOML](https://docs.rs/toml), a minimal configuration format used by[Cargo](https://doc.rust-lang.org/cargo/reference/manifest.html).[Pickle](https://github.com/birkenfeld/serde-pickle), a format common in the Python world.[RON](https://github.com/ron-rs/ron), a Rusty Object Notation.[BSON](https://github.com/mongodb/bson-rust), the data storage and network transfer format used by MongoDB.[Avro](https://docs.rs/apache-avro), a binary format used within Apache Hadoop, with support for schema definition.[JSON5](https://github.com/callum-oakley/json5-rs), a superset of JSON including some productions from ES5.[URL](https://docs.rs/serde_qs)query strings, in the x-www-form-urlencoded format.[Starlark](https://github.com/dtolnay/serde-starlark), the format used for describing build targets by the Bazel and Buck build systems.*(serialization only)*[Envy](https://github.com/softprops/envy), a way to deserialize environment variables into Rust structs.*(deserialization only)*[Envy Store](https://github.com/softprops/envy-store), a way to deserialize[AWS Parameter Store](https://docs.aws.amazon.com/systems-manager/latest/userguide/systems-manager-parameter-store.html)parameters into Rust structs.*(deserialization only)*[S-expressions](https://github.com/rotty/lexpr-rs), the textual representation of code and data used by the Lisp language family.[D-Bus](https://docs.rs/zvariant)’s binary wire format.[FlexBuffers](https://github.com/google/flatbuffers/tree/master/rust/flexbuffers), the schemaless cousin of Google’s FlatBuffers zero-copy serialization format.[Bencode](https://github.com/P3KI/bendy), a simple binary format used in the BitTorrent protocol.[Token streams](https://github.com/oxidecomputer/serde_tokenstream), for processing Rust procedural macro input.*(deserialization only)*[DynamoDB Items](https://docs.rs/serde_dynamo), the format used by[rusoto_dynamodb](https://docs.rs/rusoto_dynamodb)to transfer data to and from DynamoDB.[Hjson](https://github.com/Canop/deser-hjson), a syntax extension to JSON designed around human reading and editing.*(deserialization only)*[CSV](https://docs.rs/csv), Comma-separated values is a tabular text file format.

## Modules[§](https://docs.rs#modules)

[de](https://docs.rs/de/index.html)- Generic data structure deserialization framework.
[ser](https://docs.rs/ser/index.html)- Generic data structure serialization framework.

## Macros[§](https://docs.rs#macros)

[forward_](https://docs.rs/macro.forward_to_deserialize_any.html)to_ deserialize_ any - Helper macro when implementing the
`Deserializer`

part of a new data format for Serde.

## Traits[§](https://docs.rs#traits)

[Deserialize](https://docs.rs/trait.Deserialize.html)- A
**data structure**that can be deserialized from any data format supported by Serde. [Deserializer](https://docs.rs/trait.Deserializer.html)- A
**data format**that can deserialize any data structure supported by Serde. [Serialize](https://docs.rs/trait.Serialize.html)- A
**data structure**that can be serialized into any data format supported by Serde. [Serializer](https://docs.rs/trait.Serializer.html)- A
**data format**that can serialize any data structure supported by Serde.

## Derive Macros[§](https://docs.rs#derives)

[Deserialize](https://docs.rs/derive.Deserialize.html)`derive`

- Derive macro available if serde is built with
`features = ["derive"]`

. [Serialize](https://docs.rs/derive.Serialize.html)`derive`

- Derive macro available if serde is built with
`features = ["derive"]`

.