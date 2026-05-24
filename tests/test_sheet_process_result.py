from src.backend.domain.sheet_process_result import SheetProcessResult


def test_sheet_process_result_initializes_defaults() -> None:
    result = SheetProcessResult("Sheet1")

    assert result.sheet_name == "Sheet1"
    assert result.success is False
    assert result.error_message is None
    assert result.change_type is None
    assert result.differences is None
    assert result.add_sas_names == []
    assert result.del_sas_names == []
    assert result.sas_file_names == []
    assert result.sas_file_labels == []
    assert result.sas_name_to_label == {}
    assert result.is_split_result is False
    assert result.split_chunks == []
    assert result.original_source_file is None
    assert result.original_source_sheet_name is None
    assert result.df is None
    assert result.updated_rows_count == 0
    assert result.deleted_rows_count == 0
    assert result.added_rows_count == 0
