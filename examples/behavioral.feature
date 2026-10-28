Feature: Export a personal reading list
  Scenario: Export a populated list
    Given my reading list contains two saved books
    When I export my reading list as CSV
    Then the CSV contains a title and author column and one row per saved book

  Scenario: Export an empty list
    Given my reading list contains no books
    When I export my reading list as CSV
    Then the CSV contains only the title and author header row

  Scenario: Keep the reading list after export
    Given my reading list contains two saved books
    When I export my reading list as CSV
    Then my reading list still contains the same two books
