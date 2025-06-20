Feature: Idea Management
  As an employee in an organization
  I want to submit, manage, and collaborate on ideas
  So that I can contribute to organizational innovation

  Background:
    Given the ideas service is running
    And the database is clean and initialized

  Scenario: Employee submits a new innovation idea
    Given I am a logged-in employee with user ID "emp001"
    When I submit an idea with title "AI-Powered Customer Support Bot"
    And description "Implement an AI chatbot to handle 80% of customer inquiries automatically"
    And category "innovation"
    Then the idea should be created successfully
    And the idea status should be "draft"
    And the idea should have zero votes initially
    And the idea should be visible in my submitted ideas list

  Scenario: Employee publishes a draft idea
    Given I have a draft idea with ID "idea123"
    And I am the owner of the idea
    When I publish the idea
    Then the idea status should change to "published"
    And the idea should be visible to all employees
    And the published_at timestamp should be set

  Scenario: Multiple employees collaborate on an idea through comments
    Given there is a published idea with ID "idea456"
    And the idea has title "Remote Work Policy Enhancement"
    When employee "emp002" adds comment "This could include flexible hours"
    And employee "emp003" adds comment "We should consider time zone differences"
    And employee "emp002" adds comment "Great point about time zones!"
    Then the idea should have 3 comments
    And all comments should be visible to viewers
    And the idea view count should increase

  Scenario: Manager reviews high-engagement ideas
    Given there are multiple published ideas
    And idea "Green Office Initiative" has 25 upvotes and 4.5 rating
    And idea "Cost Reduction Strategy" has 18 upvotes and 4.2 rating
    And idea "Employee Wellness Program" has 30 upvotes and 4.8 rating
    When I filter ideas by "high engagement"
    Then I should see ideas ordered by engagement score
    And "Employee Wellness Program" should be ranked first
    And "Green Office Initiative" should be ranked second

  Scenario: Idea progresses through status workflow
    Given there is a published idea with sufficient engagement
    When a manager changes the status to "under_review"
    Then the idea status should be "under_review"
    And stakeholders should be notified
    When the decision is made to implement
    Then the idea status should change to "implemented"
    And the idea owner should receive implementation notification

  Scenario: Employee searches for ideas by category and keywords
    Given there are ideas in different categories
    And there is an "innovation" idea about "machine learning"
    And there is a "cost_saving" idea about "energy efficiency"  
    And there is an "improvement" idea about "workflow automation"
    When I search for ideas with keyword "automation"
    Then I should see the "improvement" idea in results
    When I filter by category "innovation"
    Then I should only see innovation category ideas

  Scenario: Idea view tracking and analytics
    Given there is a published idea with ID "idea789"
    When 10 different employees view the idea
    And 3 employees view it multiple times
    Then the idea view count should be 13
    And unique viewer count should be 10
    And popular ideas analytics should reflect this engagement

  Scenario: Employee manages their idea portfolio
    Given I am employee "emp004"
    And I have submitted 5 ideas in the last month
    When I view my idea dashboard
    Then I should see all 5 ideas with their current status
    And I should see engagement metrics for each idea
    And I should see which ideas need attention

  Scenario Outline: Idea validation and error handling
    Given I am a logged-in employee
    When I try to submit an idea with title "<title>" and description "<description>"
    Then the submission should <result>
    And I should receive message "<message>"

    Examples:
      | title | description | result | message |
      | | Valid description here | fail | Title is required |
      | Valid Title | | fail | Description is required |
      | AB | Short desc | fail | Title must be at least 3 characters |
      | Valid Title | Valid description that meets requirements | succeed | Idea created successfully |

  Scenario: Bulk idea import for migration
    Given I am an administrator
    When I import ideas from CSV file with 100 valid entries
    Then all 100 ideas should be created successfully
    And ideas should maintain their original timestamps
    And idea owners should be notified of successful import