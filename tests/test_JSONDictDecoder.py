from types import NoneType
from typing import Any

import pytest

from TwitchChannelPointsMiner.JSONDictDecoder import (
    instance_of_validator,
    DecoderError,
    int_validator,
    JSONDictDecoder,
    str_validator,
    bool_validator,
    expect_type_and_map,
    none_validator,
    Undefined,
)


class DataClass(object):
    def __init__(self, int_value: int, str_value: str, dict_value: dict):
        self.int_value = int_value
        self.str_value = str_value
        self.dict_value = dict_value


test_expect_value_type_data = [
    ("test_value", str),
    ("", str),
    (1234, int),
    (-1, int),
    ("", int | str),
    (11234, int | str),
    ({"key": "value"}, dict),
    ({1234: "value"}, dict),
    (DataClass(-1234, "some string", {"key": "value"}), DataClass),
]


@pytest.mark.parametrize("value,expected_type", test_expect_value_type_data)
def test_validate_type(value, expected_type):
    assert instance_of_validator(value, expected_type) is value


test_expect_value_type_error_data = [
    ("test_value", int),
    (1234, str),
    (None, str),
    (None, int),
    (1244, str | None),
    ({"key": "value"}, str),
    (DataClass(-1234, "some string", {"key": "value"}), dict),
]


@pytest.mark.parametrize("value,expected_type", test_expect_value_type_error_data)
def test_validate_type_error(value, expected_type):
    with pytest.raises(DecoderError):
        instance_of_validator(value, expected_type)


@pytest.fixture()
def context():
    return JSONDictDecoder()


test_none_decoder_data = [None]


@pytest.mark.parametrize("value", test_none_decoder_data)
def test_validator_decoder(context, value):
    assert none_validator(context, value) is None


test_none_decoder_error_data = [
    "",
    0,
    False,
    "some value",
    1234,
    -1234,
    True,
    {},
    {"key": "value"},
    DataClass(1234, "some string", {"key": "value"}),
]


@pytest.mark.parametrize("value", test_none_decoder_error_data)
def test_none_validator_error(value, context):
    with pytest.raises(DecoderError):
        none_validator(context, value)


test_int_decoder_data = [0, 1, -1, 100, 1234, -1234, 456832234568, -32762347697689]


@pytest.mark.parametrize("value", test_int_decoder_data)
def test_int_validator(context, value: Any):
    assert int_validator(context, value) is value


test_int_decoder_error_data = [
    None,
    False,
    True,
    "",
    "test value",
    {},
    {"key": "value"},
    {1234, 4321},
    DataClass(-1234, "some string", {"key": "value"}),
    {},
]


@pytest.mark.parametrize("value", test_int_decoder_error_data)
def test_int_decoder_data_error(context, value: Any):
    with pytest.raises(DecoderError):
        int_validator(context, value)


test_str_decoder_data = [
    "",
    "some value",
    "437683947",
    "       ",
    "multiline\nstring",
    "string with special characters \U0000200b and \U00000301",
    "string with emojis 😀 and 🥰",
]


@pytest.mark.parametrize("value", test_str_decoder_data)
def test_str_decoder(context, value: Any):
    assert str_validator(context, value) == value


test_int_decoder_error_data = [
    None,
    1234,
    -1234,
    0,
    False,
    True,
    {},
    {"key": "value"},
    DataClass(-1234, "some string", {"key": "value"}),
    {},
]


@pytest.mark.parametrize("value", test_int_decoder_error_data)
def test_str_decoder_error(context, value: Any):
    with pytest.raises(DecoderError):
        str_validator(context, value)


test_bool_decoder_data = [True, False]


@pytest.mark.parametrize("value", test_bool_decoder_data)
def test_bool_decoder(context, value: Any):
    assert bool_validator(context, value) is value


test_bool_decoder_error_data = [
    None,
    "",
    "0",
    0,
    "1",
    1,
    {},
    {"key": "value"},
    DataClass(-1234, "some string", {"key": "value"}),
    {},
]


@pytest.mark.parametrize("value", test_bool_decoder_error_data)
def test_bool_decoder_error(context, value: Any):
    with pytest.raises(DecoderError):
        bool_validator(context, value)


test_expect_type_and_map_data = [
    ("1234", str, lambda x: int(x), 1234),
    (None, str | None, lambda x: x if x is not None else "", ""),
    (None, NoneType, lambda x: "None", "None"),
    ({"key": "value"}, dict, lambda x: x["key"], "value"),
]


@pytest.mark.parametrize(
    "value,expected_input_type,mapper,expected_result", test_expect_type_and_map_data
)
def test_expect_type_and_map(
    context, value, expected_input_type, mapper, expected_result
):
    assert (
        expect_type_and_map(context, value, expected_input_type, mapper)
        == expected_result
    )


test_expect_type_and_map_error_data = [
    (None, str, lambda x: ""),
]


@pytest.mark.parametrize(
    "value,expected_input_type,mapper", test_expect_type_and_map_error_data
)
def test_expect_type_and_map_error(context, value, expected_input_type, mapper):
    with pytest.raises(DecoderError):
        expect_type_and_map(context, value, expected_input_type, mapper)


class WrapperClass:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        # Override equality to allow an easy way to assert equality in tests
        return isinstance(other, WrapperClass) and self.value == other.value

    def __repr__(self):
        return f"WrapperClass({self.value})"


def decode_wrapper_class(context: JSONDictDecoder, data: Any):
    return WrapperClass(context.decode_property(data, "test key", str))


class ComplexDataClass:
    def __init__(
        self,
        int_value: int,
        nullable_str: str | None,
        child_object: WrapperClass,
        bool_value: bool,
        optional_float: float | None,
    ):
        self.int_value = int_value
        self.optional_str = nullable_str
        self.child_object = child_object
        self.bool_value = bool_value
        self.optional_float = optional_float

    def __eq__(self, other):
        return (
            isinstance(other, ComplexDataClass)
            and self.int_value == other.int_value
            and self.optional_str == other.optional_str
            and self.child_object == other.child_object
            and self.bool_value == other.bool_value
            and self.optional_float == other.optional_float
        )

    def __repr__(self):
        return f"ComplexDataClass({self.int_value}, {self.optional_str}, {self.child_object}, {self.bool_value}, {self.optional_float})"


def complex_data_class_decoder(context: JSONDictDecoder, data: Any):
    int_value = context.decode_property(data, "int_value", int)
    nullable_str = context.decode_property(data, "nullable_str", str | None)
    child_object = context.decode_property(data, "child_object", WrapperClass)
    bool_value = context.decode_property(data, "bool_value", bool)
    optional_float = context.decode_optional_property(
        data, "optional_float", float | None
    )
    return ComplexDataClass(
        int_value,
        nullable_str,
        child_object,
        bool_value,
        optional_float if not isinstance(optional_float, Undefined) else None,
    )


class TestJSONDictDecoder:
    @pytest.fixture
    def decoder(self):
        return JSONDictDecoder().with_decoders(
            {WrapperClass: decode_wrapper_class, ComplexDataClass: complex_data_class_decoder}
        )

    test_decode_union_data = [
        (None, str | None, None),
        ("some value", str | None, "some value"),
        (1234, str | int | None, 1234),
    ]

    @pytest.mark.parametrize(
        "data,expected_type,expected_value", test_decode_union_data
    )
    def test_decode_union(self, decoder, data, expected_type, expected_value):
        assert decoder.decode(data, expected_type) == expected_value

    test_decode_union_error_data = [
        (None, str | int),
        ("some value", bool | None | int | float),
    ]

    @pytest.mark.parametrize("data,expected_type", test_decode_union_error_data)
    def test_decode_union_error(self, decoder, data, expected_type):
        with pytest.raises(DecoderError):
            decoder.decode(data, expected_type)

    test_decode_data = [
        (None, NoneType, None),
        (0, int, 0),
        ("value", int | str, "value"),
        ({"test key": "test value"}, dict, {"test key": "test value"}),
        ({"test key": "test value"}, WrapperClass, WrapperClass("test value")),
        (["one", "two", "three", "four"], list[str], ["one", "two", "three", "four"]),
        (
            {
                "int_value": 1234,
                "nullable_str": None,
                "child_object": {
                    "test key": "some value",
                },
                "bool_value": True,
                "optional_float": None,
            },
            ComplexDataClass,
            ComplexDataClass(1234, None, WrapperClass("some value"), True, None),
        ),
        (
            {
                "int_value": 1234,
                "nullable_str": "value",
                "child_object": {
                    "test key": "some value",
                },
                "bool_value": False,
            },
            ComplexDataClass,
            ComplexDataClass(1234, "value", WrapperClass("some value"), False, None),
        ),
    ]

    @pytest.mark.parametrize("data,expected_type,expected_value", test_decode_data)
    def test_decode(self, decoder, data, expected_type, expected_value):
        assert decoder.decode(data, expected_type) == expected_value

    test_decode_error_data = [
        (None, str),
        ("some value", None),
        (True, int),
        (False, int),
        (False, str),
        (True, str),
        (0, bool),
        (1, bool),
        ("test value", WrapperClass),
        (
            {
                "int_value": 1234,
                "nullable_str": "some string",
                "child_object": None,
                "bool_value": 123.456,
            },
            ComplexDataClass,
        ),
        ("some value", ComplexDataClass),
    ]

    @pytest.mark.parametrize("data,expected_type", test_decode_error_data)
    def test_decode_error(self, decoder, data, expected_type):
        with pytest.raises(DecoderError):
            decoder.decode(data, expected_type)

    test_decode_list_data = [
        ([], Any, []),
        (["some value"], Any, ["some value"]),
        (["some value", "another value", ""], str, ["some value", "another value", ""]),
        (
            ["some value", 100, True, None],
            str | int | bool | None,
            ["some value", 100, True, None],
        ),
        ([None, 0, -1, None, 100, 1234], int | None, [None, 0, -1, None, 100, 1234]),
    ]

    @pytest.mark.parametrize("data,expected_type,expected_value", test_decode_list_data)
    def test_decode_list(self, decoder, data, expected_type, expected_value):
        assert decoder.decode_list(data, expected_type) == expected_value

    test_decode_list_error_data = [
        ([True], int),
        ([False], int),
        ([True, False], int),
        (["some value", 1234], None | bool),
    ]

    @pytest.mark.parametrize("data,expected_type", test_decode_list_error_data)
    def test_decode_list_error(self, decoder, data, expected_type):
        with pytest.raises(DecoderError):
            decoder.decode_list(data, expected_type)

    test_decode_property_data = [
        ({"some_key": "some_value"}, "some_key", str, "some_value"),
        ({"first": {"second": "value"}}, "first", dict, {"second": "value"}),
        ({"first": {"test key": "value"}}, "first", WrapperClass, WrapperClass("value")),
        (["first", "second", "third", 4, 5, "sixth", None], 2, str, "third"),
        (["first", 2, None, 0], 0, str, "first"),
    ]

    @pytest.mark.parametrize(
        "data,path,result_type,expected_value", test_decode_property_data
    )
    def test_decode_property(self, decoder, data, path, result_type, expected_value):
        assert decoder.decode_property(data, path, result_type) == expected_value

    test_decode_property_error_data = [
        ({}, "some key", Any),
        ({"some_key": "some_value"}, "another key", str),
        ({"first": {"second": "value"}}, "first", None),
        ({"first": {"no key": "value"}}, "first", WrapperClass),
        ([], 1, Any),
        (["first", "second"], 2, Any),
        (["first", "second"], -1, Any),
        (["first", "second", "third", 4, 5, "sixth", None], 2, int),
        (["first", 2, None, 0], 0, bool),
    ]

    @pytest.mark.parametrize("data,path,expected_type", test_decode_property_error_data)
    def test_decode_property_error(self, decoder, data, path, expected_type):
        with pytest.raises(DecoderError):
            decoder.decode_property(data, path, expected_type)
