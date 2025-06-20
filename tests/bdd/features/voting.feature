Feature: Voting System
  As an employee
  I want to vote on ideas and see aggregated voting results
  So that the best ideas can be identified and prioritized

  Background:
    Given the voting service is running
    And the Redis cache is available
    And there are published ideas available for voting

  Scenario: Employee casts upvote on innovative idea
    Given I am employee "emp001"
    And there is a published idea with ID "idea123"
    When I cast an upvote on the idea
    Then the vote should be recorded successfully
    And the idea's upvote count should increase by 1
    And my vote should be cached for quick retrieval
    And I should not be able to vote again on the same idea

  Scenario: Employee changes vote from upvote to downvote
    Given I am employee "emp002"
    And I have already upvoted idea "idea456"
    When I change my vote to downvote
    Then my previous upvote should be removed
    And a downvote should be recorded
    And the idea's vote counts should be updated accordingly
    And the net score should decrease by 2

  Scenario: Employee provides detailed rating with feedback
    Given I am employee "emp003"
    And there is an idea about "Flexible Work Arrangements"
    When I give a rating of 4.5 out of 5
    And I provide feedback "Great idea but needs cost analysis"
    Then the rating should be recorded
    And the idea's average rating should be recalculated
    And my rating should contribute to the overall score

  Scenario: Real-time vote aggregation and leaderboard
    Given there are 10 ideas competing for implementation
    When multiple employees vote simultaneously:
      | employee | idea_id | vote_type | rating |
      | emp001 | idea001 | upvote | 4.8 |
      | emp002 | idea001 | upvote | 4.2 |
      | emp003 | idea002 | upvote | 3.9 |
      | emp004 | idea001 | rating | 4.6 |
      | emp005 | idea003 | upvote | 4.1 |
    Then vote aggregates should be updated in real-time
    And idea001 should be ranked highest
    And leaderboard should reflect current standings
    And Redis cache should contain latest vote counts

  Scenario: Voting fraud prevention and validation
    Given I am employee "emp004"
    And I have already voted on idea "idea789"
    When I try to vote again using a different session
    Then the duplicate vote should be rejected
    And an audit log entry should be created
    And I should receive an appropriate error message
    When someone tries to vote with an invalid user ID
    Then the vote should be rejected
    And security alert should be logged

  Scenario: Vote analytics and reporting
    Given there are votes from the last 30 days
    When I request voting analytics report
    Then I should see total votes cast
    And average engagement per idea
    And top-voted ideas by category
    And voting trends over time
    And employee participation rates

  Scenario: Controversial idea identification
    Given there is an idea receiving mixed feedback
    When it receives 15 upvotes and 12 downvotes
    And ratings range from 2.1 to 4.8
    Then the idea should be flagged as "controversial"
    And controversy score should be calculated
    And it should be highlighted for manager review
    And balanced feedback should be encouraged

  Scenario: Vote weight calculation based on expertise
    Given employee "exp001" is tagged as domain expert in "AI/ML"
    And there is an AI-related idea
    When the expert votes on the AI idea
    Then their vote should have higher weight (1.5x)
    And weighted score should be calculated
    And expert endorsement should be highlighted

  Scenario: Bulk voting operations for administrators
    Given I am an administrator
    And there are 50 ideas that need initial seeding votes
    When I perform bulk voting operation
    Then votes should be distributed realistically
    And voting patterns should appear natural
    And no single user should dominate vote counts

  Scenario: Vote history and audit trail
    Given I am employee "emp005"
    When I view my voting history
    Then I should see all ideas I've voted on
    And timestamps of my votes
    And any vote changes I've made
    When administrator reviews vote audit trail
    Then all voting activities should be logged
    And suspicious patterns should be detectable

  Scenario: Time-based voting campaigns
    Given there is a quarterly innovation challenge
    When voting campaign starts for Q1 ideas
    Then employees should be notified
    And special voting interface should be available
    And vote counts should be tracked separately
    And campaign results should be calculated at end period

  Scenario: Anonymous vs identified voting options
    Given there is a sensitive idea about "Management Changes"
    When anonymous voting is enabled for this idea
    Then employees can vote without identity disclosure
    And vote counts should still be accurate
    And voting patterns should be tracked for authenticity
    But individual voter identity should remain private

  Scenario Outline: Vote validation and error handling
    Given I am employee "<employee_id>"
    When I try to vote "<vote_type>" with rating "<rating>" on idea "<idea_id>"
    Then the vote should <result>
    And I should receive message "<message>"

    Examples:
      | employee_id | vote_type | rating | idea_id | result | message |
      | | upvote | | idea123 | fail | User authentication required |
      | emp001 | upvote | | nonexistent | fail | Idea not found |
      | emp001 | rating | 6.0 | idea123 | fail | Rating must be between 1 and 5 |
      | emp001 | invalid | | idea123 | fail | Invalid vote type |
      | emp001 | upvote | | idea123 | succeed | Vote recorded successfully |