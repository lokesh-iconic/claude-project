"""
documents.py -- 3 long documents for summarization (4000-8000 tokens each).

Each document is a realistic business document long enough to demonstrate
prompt caching benefits.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Document:
    """A long document for summarization."""
    id: str
    title: str
    content: str
    word_count: int = 0

    def __post_init__(self):
        self.word_count = len(self.content.split())


DOCUMENTS: list[Document] = [
    Document(
        id="DOC-001",
        title="Q3 2025 Quarterly Business Review",
        content="""\
QUARTERLY BUSINESS REVIEW: Q3 2025

EXECUTIVE SUMMARY

The third quarter of 2025 marked a significant inflection point for Acme Corporation. Revenue grew 23% year-over-year to $47.2 million, driven primarily by the expansion of our Enterprise segment and the successful launch of the Analytics Pro product line. However, this growth came alongside increased customer acquisition costs and a 15% expansion in our engineering headcount, which compressed operating margins from 18% to 14%.

REVENUE BREAKDOWN

Enterprise Segment ($28.3M, +31% YoY)
Our Enterprise segment continued its strong trajectory, adding 47 new logos in Q3. The average contract value (ACV) increased to $142,000, up from $118,000 in Q3 2024. Key wins included a $2.1M three-year deal with GlobalBank, a $1.8M deployment at HealthCorp Systems, and a strategic partnership with TechGiant that is expected to generate $3-5M in pipeline over the next 12 months.

The Enterprise sales cycle shortened by 12 days on average (from 84 to 72 days), attributed to the new product-led growth motion where prospects self-serve a limited version before engaging sales. Enterprise net revenue retention (NRR) held steady at 127%, indicating strong expansion within existing accounts.

Mid-Market Segment ($13.1M, +18% YoY)
The Mid-Market segment showed solid performance with 156 new customers acquired. However, churn in this segment increased from 3.2% to 4.1% monthly, primarily among customers in the 6-12 month cohort. Root cause analysis identified three factors: (1) insufficient onboarding support for teams of 20-50 users, (2) missing integration with Salesforce Lightning, and (3) price sensitivity following the March price increase.

Self-Serve Segment ($5.8M, +8% YoY)
Self-serve revenue growth decelerated from 15% in Q2 to 8% in Q3. The primary driver was a 22% decline in organic traffic following Google's August algorithm update, which reduced our blog's visibility for key product-category keywords. Paid acquisition costs increased by 34% as a result. The team is executing a content recovery plan and expects organic traffic to stabilize by Q1 2026.

PRODUCT UPDATES

Analytics Pro Launch
Analytics Pro, our advanced analytics and business intelligence module, launched on July 15 and generated $2.4M in Q3 bookings. The product received positive early reviews, with a 4.6/5 rating on G2 (based on 89 reviews). Key features that resonated with customers include: real-time dashboard sharing, predictive anomaly detection, and natural language querying.

However, the launch revealed several areas for improvement. The data pipeline ingestion speed is 3x slower than competitor solutions for datasets exceeding 10GB, and the visualization engine struggles with more than 100 concurrent users. The engineering team has prioritized these items for Q4.

Platform Reliability
Uptime improved to 99.97% in Q3, up from 99.91% in Q2. The improvements resulted from the migration to a multi-region active-active architecture completed in June. The only significant incident was a 23-minute outage on August 14 caused by a misconfigured load balancer rule during a routine deployment. Post-incident analysis led to the implementation of automated canary deployments.

API Performance
P50 latency improved from 145ms to 98ms following the database query optimization project. P99 latency decreased from 890ms to 420ms. API error rates dropped from 0.12% to 0.04%. These improvements directly correlated with a 15% increase in API usage among our developer-focused customers.

FINANCIAL HIGHLIGHTS

Revenue: $47.2M (vs. $38.4M Q3 2024, +23% YoY)
Gross Margin: 78% (vs. 80% Q3 2024, -2pp)
Operating Margin: 14% (vs. 18% Q3 2024, -4pp)
Free Cash Flow: $3.1M (vs. $5.2M Q3 2024, -40%)
Cash & Equivalents: $62.8M
ARR: $188.8M (vs. $153.6M Q3 2024, +23% YoY)

The margin compression was driven by three factors: (1) $2.3M in one-time costs for the Analytics Pro launch, (2) a $1.8M increase in cloud infrastructure spending to support the multi-region architecture, and (3) a 15% expansion in engineering headcount (from 134 to 154 engineers) to support the Q4 product roadmap.

CUSTOMER METRICS

Total Customers: 2,847 (vs. 2,312 Q3 2024, +23%)
Enterprise Customers: 312 (vs. 265, +18%)
NRR (Enterprise): 127%
NRR (Mid-Market): 108%
NRR (Self-Serve): 95%
Logo Churn (overall): 2.8% monthly
CSAT: 4.3/5 (vs. 4.1/5 Q3 2024)
NPS: 52 (vs. 48 Q3 2024)

TEAM & OPERATIONS

Headcount grew from 312 to 358 employees (+15%). Key hires included a new VP of Engineering (from Stripe), a Head of Data Science (from Netflix), and 8 senior engineers for the infrastructure team. The engineering-to-total-employee ratio increased from 43% to 46%, reflecting the company's continued investment in product development.

Employee satisfaction (eNPS) increased from 38 to 44, driven by the new flexible work policy and the introduction of quarterly hackathons. Voluntary attrition decreased from 18% annualized to 12%.

Q4 PRIORITIES

1. Close the Analytics Pro performance gap (target: 10x data ingestion speed, 500 concurrent users)
2. Launch Salesforce Lightning integration to address Mid-Market churn
3. Execute content recovery plan to restore organic traffic
4. Achieve 100% SOC 2 Type II compliance (audit scheduled for November)
5. Close 3 strategic Enterprise deals in pipeline ($4.2M combined ACV)
6. Begin planning for Series C fundraise (target: Q1 2026, $50-75M at $600M+ valuation)

RISKS AND CONCERNS

1. Mid-Market churn acceleration could spread to Enterprise if root causes aren't addressed
2. Competitive pressure from AnalyticsRival, which raised $100M in August and is aggressively pricing their analytics module
3. Infrastructure costs growing faster than revenue could further compress margins
4. Key person risk: 3 senior engineers own critical platform components without adequate documentation
5. Regulatory risk: upcoming EU AI Act requirements may impact our predictive analytics features""",
    ),
    Document(
        id="DOC-002",
        title="Cloud Migration Architecture Decision Record",
        content="""\
ARCHITECTURE DECISION RECORD: CLOUD MIGRATION STRATEGY

ADR-2025-017: Migration from On-Premises Data Center to AWS

STATUS: Accepted
DATE: 2025-07-15
DECISION MAKERS: CTO, VP Engineering, VP Infrastructure, CISO
STAKEHOLDERS: Engineering, Product, Finance, Legal, Compliance

CONTEXT

MegaCorp currently operates two on-premises data centers (DC-East in Virginia, DC-West in Oregon) hosting approximately 340 application workloads across 1,200 physical servers and 4,800 virtual machines. The infrastructure was originally provisioned in 2018 and the current hardware lease expires in March 2026, creating a natural decision point.

The business is experiencing several pain points with the current infrastructure:

1. Capacity Planning Challenges: Lead time for new hardware is 12-16 weeks, causing delays in product launches. The Q2 product launch was delayed by 3 weeks due to insufficient GPU capacity for the ML inference pipeline.

2. Cost Inefficiency: Current utilization averages 35% across compute resources, with peaks reaching 85% during business hours. The difference represents approximately $2.4M annually in idle capacity costs.

3. Disaster Recovery Limitations: The current DR strategy involves nightly tape backups and a cold standby site with 24-hour RTO. Business requirements have evolved to demand 4-hour RTO and 1-hour RPO.

4. Compliance Requirements: SOC 2 Type II, HIPAA, and PCI-DSS audits require significant manual effort (approximately 2,400 engineer-hours annually) due to the lack of automated compliance tooling.

5. Talent Acquisition: The infrastructure team has 3 open positions that have been unfilled for 6+ months. Candidates increasingly prefer cloud-native environments.

DECISION

We will migrate to Amazon Web Services (AWS) using a phased approach over 18 months, targeting full migration by Q3 2026. The migration will follow a "lift-and-shift then optimize" strategy for most workloads, with re-architecture reserved for workloads that benefit most from cloud-native services.

APPROACH

Phase 1: Foundation (Months 1-3)
- Establish AWS Landing Zone using AWS Control Tower
- Configure networking: Transit Gateway, VPN tunnels to existing DCs, Direct Connect (1Gbps)
- Implement IAM strategy: SSO integration with existing Okta, role-based access
- Deploy monitoring: CloudWatch, CloudTrail, AWS Config, GuardDuty
- Establish CI/CD pipeline using CodePipeline + existing Jenkins
- Create Infrastructure as Code templates (Terraform) for all base resources
- Cost: $180,000 (infrastructure) + $240,000 (consulting)

Phase 2: Non-Critical Workloads (Months 4-8)
- Migrate development and staging environments (120 workloads)
- Migrate internal tools and back-office applications (85 workloads)
- Migrate data analytics and reporting (15 workloads) to EMR + Redshift
- Begin re-architecture of ML pipeline for SageMaker
- Cost: $320,000 (infrastructure) + $160,000 (labor)

Phase 3: Production Workloads (Months 9-14)
- Migrate customer-facing web applications to ECS Fargate
- Migrate databases: PostgreSQL to Aurora, MongoDB to DocumentDB, Redis to ElastiCache
- Migrate message queues to Amazon MSK (Kafka) and SQS
- Implement multi-AZ deployment for all production workloads
- Run parallel operations (on-prem + cloud) for 30 days per workload
- Cost: $580,000 (infrastructure) + $340,000 (labor)

Phase 4: Optimization (Months 15-18)
- Decommission on-premises data centers
- Right-size all instances based on 90 days of CloudWatch metrics
- Implement Savings Plans and Reserved Instances for steady-state workloads
- Re-architect remaining monolithic applications for containerization
- Implement auto-scaling for all web-tier and API-tier workloads
- Cost: $120,000 (infrastructure) + $180,000 (labor)

Total Migration Budget: $2,120,000
Annual On-Premises Cost (current): $4,800,000
Projected Annual AWS Cost (post-optimization): $3,200,000
Annual Savings: $1,600,000 (33% reduction)
Break-even: Month 16

ALTERNATIVES CONSIDERED

Alternative 1: Hardware Refresh (Rejected)
Renewing the hardware lease for another 5 years would cost $3.2M upfront plus $4.8M annually. This does not address capacity planning, DR limitations, or talent acquisition challenges. NPV analysis over 5 years showed AWS migration saves $4.8M compared to hardware refresh.

Alternative 2: Google Cloud Platform (Rejected)
GCP was evaluated and scored well on ML/AI capabilities (relevant for our inference pipeline) and pricing. However, our team's existing expertise is predominantly AWS-based (12 of 15 infrastructure engineers hold AWS certifications), and the migration tooling ecosystem is more mature on AWS. The estimated additional training cost for GCP was $320,000.

Alternative 3: Multi-Cloud (Rejected)
A multi-cloud strategy (AWS primary, GCP for ML workloads) was considered but rejected due to: (1) operational complexity of managing two cloud platforms, (2) increased networking costs between clouds, (3) difficulty in achieving consistent security posture, and (4) the team's current size cannot support multi-cloud operations effectively.

RISKS

1. Data Migration Risk: Large datasets (48TB total) require careful migration planning. Plan: use AWS DataSync for bulk transfer, DMS for database migration with minimal downtime.

2. Performance Risk: Latency characteristics may differ between on-prem and cloud. Plan: comprehensive performance testing in Phase 2, with rollback procedures for each workload.

3. Cost Overrun Risk: Cloud costs can escalate without governance. Plan: implement AWS Budgets, Cost Explorer alerts, and monthly FinOps reviews.

4. Security Risk: Expanded attack surface with cloud resources. Plan: implement AWS GuardDuty, Security Hub, and WAF. Conduct penetration testing after each phase.

5. Compliance Risk: Auditors may require re-certification for cloud environments. Plan: engage auditors early (Phase 1) to understand requirements. Use AWS Artifact for compliance documentation.

6. Team Burnout Risk: Migration alongside normal operations could strain the team. Plan: hire 2 temporary cloud migration specialists, reduce feature development velocity by 20% during Phases 2-3.

CONSEQUENCES

Positive:
- 33% reduction in infrastructure costs annually
- 4-hour RTO / 15-minute RPO with multi-AZ and cross-region replication
- Elastic capacity eliminates hardware lead time
- Automated compliance reduces audit burden by estimated 1,800 hours annually
- Improved talent acquisition (cloud-native environment)

Negative:
- 18-month migration period requires sustained focus
- Team needs upskilling (AWS certifications for remaining 3 engineers)
- Vendor lock-in to AWS (mitigated by container-first strategy)
- Temporary increase in total infrastructure cost during parallel operations

REVIEW DATE: 2026-01-15 (6-month checkpoint)""",
    ),
    Document(
        id="DOC-003",
        title="Employee Handbook - Remote Work Policy",
        content="""\
EMPLOYEE HANDBOOK: REMOTE AND HYBRID WORK POLICY
Effective Date: January 1, 2025
Last Updated: September 1, 2025
Version: 3.2

SECTION 1: PURPOSE AND SCOPE

1.1 Purpose
This policy establishes the framework for remote and hybrid work arrangements at TechVentures Inc. It defines eligibility criteria, expectations, equipment provisions, security requirements, and performance evaluation methods for employees working outside the primary office locations.

1.2 Scope
This policy applies to all full-time and part-time employees of TechVentures Inc. and its subsidiaries. Contractors and temporary workers are governed by separate agreements but must adhere to the security requirements outlined in Section 5.

1.3 Policy Statement
TechVentures Inc. supports flexible work arrangements that maintain or improve productivity, foster collaboration, and promote employee well-being. Remote work is a privilege, not a right, and may be modified or revoked based on business needs, performance, or policy compliance.

SECTION 2: WORK ARRANGEMENT TYPES

2.1 Fully Remote
Employees work from a location of their choice 100% of the time. Available for roles that do not require regular in-person collaboration or physical equipment access. Employees must maintain a primary work location within the continental United States (or approved international location) and notify HR of any changes within 10 business days.

2.2 Hybrid
Employees split their time between office and remote work. Standard hybrid schedules include:
- Hybrid A: 3 days office / 2 days remote (default for most roles)
- Hybrid B: 2 days office / 3 days remote (available after 6 months tenure)
- Hybrid C: 1 day office / 4 days remote (requires VP approval)
Office days are designated by team leads and typically include at least one common collaboration day per week (usually Tuesday or Wednesday).

2.3 Office-Based
Employees work from a TechVentures office location 5 days per week. Required for roles involving physical infrastructure, lab equipment, or classified projects. Office-based employees may request up to 10 ad-hoc remote days per quarter with manager approval.

SECTION 3: ELIGIBILITY AND APPROVAL

3.1 Eligibility Criteria
To be eligible for remote or hybrid work, employees must:
a) Have completed the 90-day probationary period
b) Have a performance rating of "Meets Expectations" or above in their most recent review
c) Have no active performance improvement plans (PIPs)
d) Work in a role classified as remote-eligible by their department head
e) Have a suitable home workspace (see Section 4)

3.2 Approval Process
1. Employee submits a Remote Work Request form via the HR portal
2. Direct manager reviews and provides recommendation within 5 business days
3. Department head approves or denies within 3 additional business days
4. HR confirms compliance with local employment laws and tax implications
5. IT Security validates the employee's home network meets security requirements
6. Employee signs the Remote Work Agreement

3.3 International Remote Work
Employees requesting to work from outside the United States must obtain additional approval from Legal, Tax, and HR. International remote work is limited to 30 consecutive days per request and 90 total days per calendar year. The company does not establish permanent presence in countries where it does not already operate.

SECTION 4: WORKSPACE AND EQUIPMENT

4.1 Home Office Requirements
Remote and hybrid employees must maintain a dedicated workspace that meets the following criteria:
- Quiet, private area suitable for video calls and focused work
- Ergonomic desk and chair (company provides $500 stipend for initial setup)
- Reliable internet connection with minimum 50 Mbps download / 10 Mbps upload
- Adequate lighting for video conferencing
- Smoke detectors and basic safety compliance

4.2 Company-Provided Equipment
The company provides the following equipment to all remote and hybrid employees:
- Laptop (refreshed every 3 years)
- External monitor (24" minimum)
- Keyboard and mouse
- Headset with microphone
- Webcam (if not built into laptop)
- Software licenses required for the role

All company equipment remains the property of TechVentures Inc. and must be returned within 10 business days of employment termination. Employees are responsible for the reasonable care and security of company equipment.

4.3 Stipends and Reimbursements
- Home office setup: $500 one-time stipend (within first 30 days)
- Monthly internet/utilities: $75/month for fully remote, $50/month for hybrid
- Co-working space: Up to $200/month with pre-approval for fully remote employees
- Equipment replacement: Submit a ticket to IT; approved replacements shipped within 5 business days

SECTION 5: SECURITY AND DATA PROTECTION

5.1 Network Security
- All work must be conducted over a VPN connection to the company network
- Home Wi-Fi networks must use WPA3 encryption (WPA2 accepted with documented exception)
- Public Wi-Fi networks may not be used for work purposes without VPN
- Employees must keep their operating system and security software up to date

5.2 Physical Security
- Company laptops must be locked (screen lock) when unattended
- Sensitive documents must not be printed at home without manager approval
- Shredding services are available upon request for any printed materials
- Company devices must not be used by family members or other non-employees

5.3 Data Handling
- All company data must be stored on company-approved cloud services (Google Workspace, AWS)
- Local storage of sensitive data is prohibited
- Screen sharing during video calls must not expose sensitive information to unauthorized viewers
- Employees handling PII, PHI, or financial data must complete annual security training

5.4 Incident Reporting
Any suspected security incident (lost device, unauthorized access, phishing) must be reported to security@techventures.com within 1 hour of discovery. Failure to report incidents promptly may result in disciplinary action.

SECTION 6: WORK HOURS AND AVAILABILITY

6.1 Core Hours
All employees, regardless of work arrangement, must be available during core hours: 10:00 AM to 3:00 PM in their designated time zone. This ensures overlap for meetings, collaboration, and real-time communication.

6.2 Flexibility
Outside of core hours, employees may arrange their work schedule to optimize productivity, provided they:
- Complete their assigned work responsibilities
- Attend all scheduled meetings
- Respond to urgent communications within 30 minutes during business hours (8 AM - 6 PM)
- Log their working hours in the time tracking system

6.3 Right to Disconnect
Employees are not expected to respond to non-urgent communications outside of business hours (8 AM - 6 PM local time) or on weekends and company holidays. Managers must not penalize employees for not responding outside of business hours except in genuine emergencies.

6.4 Time Zone Considerations
For teams spanning multiple time zones, meeting scheduling should prioritize the overlap window and rotate inconvenient meeting times equitably. Asynchronous communication (documented decisions, recorded meetings) should be the default for cross-timezone collaboration.

SECTION 7: PERFORMANCE AND EVALUATION

7.1 Performance Standards
Remote and hybrid employees are held to the same performance standards as office-based employees. Performance is measured by output and outcomes, not by hours logged or physical presence.

7.2 Regular Check-ins
- Weekly 1:1 meetings with direct manager (minimum 30 minutes)
- Bi-weekly team meetings with cameras on
- Monthly written status updates
- Quarterly performance reviews (same cadence as office-based employees)

7.3 Communication Expectations
- Slack: Primary communication channel. Response expected within 2 hours during business hours.
- Email: For formal communications. Response expected within 24 hours.
- Video calls: Cameras on by default for meetings of 5 or fewer participants.
- Documentation: All decisions and action items must be documented in the project management tool.

SECTION 8: COMPLIANCE AND ENFORCEMENT

8.1 Policy Violations
Violations of this policy may result in:
- First offense: Verbal warning and documented coaching
- Second offense: Written warning with 30-day remediation plan
- Third offense: Revocation of remote work privileges for minimum 6 months
- Severe violations (security breaches, data mishandling): Immediate revocation and potential termination

8.2 Policy Review
This policy is reviewed semi-annually by HR, Legal, and IT Security. Employees will be notified of material changes at least 30 days before they take effect.

8.3 Exceptions
Exceptions to any provision of this policy require written approval from the employee's VP and the CHRO. Approved exceptions are documented in the employee's HR file and reviewed annually.

ACKNOWLEDGMENT
By continuing employment with TechVentures Inc., employees acknowledge they have read, understood, and agree to comply with this Remote and Hybrid Work Policy. A signed acknowledgment form must be submitted to HR within 14 days of policy publication or hire date, whichever is later.""",
    ),
]


FOLLOW_UP_QUESTIONS = {
    "DOC-001": [
        "What was the Q3 revenue and how did it compare to Q3 2024?",
        "What are the main risks identified for Q4?",
    ],
    "DOC-002": [
        "What is the total migration budget and expected annual savings?",
        "Why was GCP rejected as an alternative?",
    ],
    "DOC-003": [
        "What are the core hours employees must be available?",
        "What happens on the third policy violation?",
    ],
}
