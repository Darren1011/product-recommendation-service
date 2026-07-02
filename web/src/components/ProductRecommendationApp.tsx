'use client';

import {
  ArrowRight,
  Building2,
  CheckCircle2,
  Circle,
  Loader2,
  MessageSquareText,
  RotateCcw,
  Send,
  Sparkles,
} from 'lucide-react';
import type { FormEvent, ReactNode } from 'react';
import { useEffect, useMemo, useState } from 'react';

import {
  fetchAccounts,
  fetchOpportunities,
  fetchWorkflowResult,
  fetchWorkflowStatus,
  sendChatMessage,
} from '@/lib/api';
import type {
  Account,
  ChatMessage,
  Opportunity,
  RecommendationOption,
  WorkflowResult,
  WorkflowStep,
} from '@/lib/types';

const SAMPLE_REQUESTS = [
  {
    label: 'Use selected context only',
    prompt: '',
  },
  {
    label: 'Clinician laptop request',
    prompt: 'Secure lightweight laptop for clinicians with long battery and touch',
  },
  {
    label: 'Mobile workstation request',
    prompt: 'Mobile workstation for CAD rendering with 64GB memory and discrete graphics',
  },
  {
    label: 'Budget classroom request',
    prompt: 'Budget classroom devices for a shared student lab under $900',
  },
];
const DEFAULT_PROMPT = SAMPLE_REQUESTS[1].prompt;
const POLL_INTERVAL_MS = 700;
const WORKFLOW_TIMEOUT_MS = 20000;

export function ProductRecommendationApp() {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [opportunities, setOpportunities] = useState<Opportunity[]>([]);
  const [selectedAccountId, setSelectedAccountId] = useState('');
  const [selectedOpportunityId, setSelectedOpportunityId] = useState('');
  const [prompt, setPrompt] = useState(DEFAULT_PROMPT);
  const [chatId, setChatId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [workflowResult, setWorkflowResult] = useState<WorkflowResult | null>(null);
  const [workflowSteps, setWorkflowSteps] = useState<WorkflowStep[]>([]);
  const [workflowStatus, setWorkflowStatus] = useState('idle');
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Load account context once when the workspace opens.
  useEffect(() => {
    let isMounted = true;
    fetchAccounts()
      .then((items) => {
        if (!isMounted) return;
        setAccounts(items);
        setSelectedAccountId(items[0]?.id ?? '');
      })
      .catch((error: unknown) => {
        if (!isMounted) return;
        setErrorMessage(readErrorMessage(error));
      });
    return () => {
      isMounted = false;
    };
  }, []);

  // Refresh opportunities whenever the selected account changes.
  useEffect(() => {
    if (!selectedAccountId) {
      setOpportunities([]);
      setSelectedOpportunityId('');
      return;
    }

    let isMounted = true;
    fetchOpportunities(selectedAccountId)
      .then((items) => {
        if (!isMounted) return;
        setOpportunities(items);
        setSelectedOpportunityId(items[0]?.id ?? '');
      })
      .catch((error: unknown) => {
        if (!isMounted) return;
        setErrorMessage(readErrorMessage(error));
      });
    return () => {
      isMounted = false;
    };
  }, [selectedAccountId]);

  // Resolve selected objects for cards and request payloads.
  const selectedAccount = useMemo(
    () => accounts.find((account) => account.id === selectedAccountId) ?? null,
    [accounts, selectedAccountId],
  );
  const selectedOpportunity = useMemo(
    () =>
      opportunities.find((opportunity) => opportunity.id === selectedOpportunityId) ?? null,
    [opportunities, selectedOpportunityId],
  );

  // Submit the chat-shaped request and then load its workflow result.
  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmedPrompt = prompt.trim();
    if (isLoading) return;

    setIsLoading(true);
    setErrorMessage(null);
    setWorkflowResult(null);
    setWorkflowSteps([]);
    setWorkflowStatus('running');
    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmedPrompt || 'Use selected account/opportunity context.',
    };
    setMessages((current) => [...current, userMessage]);

    try {
      const chatResponse = await sendChatMessage({
        input_text: trimmedPrompt,
        chat_id: chatId,
        account_id: selectedAccountId || null,
        opportunity_id: selectedOpportunityId || null,
      });
      setChatId(chatResponse.chat_id);
      setMessages((current) => [
        ...current,
        {
          id: chatResponse.message_id,
          role: 'assistant',
          content: chatResponse.content,
          workflowId: chatResponse.workflow_id,
        },
      ]);

      // Poll stage receipts before loading completed recommendation cards.
      if (chatResponse.workflow_id) {
        const envelope = await waitForWorkflowResult(chatResponse.workflow_id, (steps, status) => {
          setWorkflowSteps(steps);
          setWorkflowStatus(status);
        });
        setWorkflowResult(envelope.result);
        setWorkflowSteps(envelope.result.steps);
        setWorkflowStatus('completed');
      }
    } catch (error) {
      setErrorMessage(readErrorMessage(error));
      setWorkflowStatus('failed');
    } finally {
      setIsLoading(false);
    }
  }

  // Reset only the interactive session, not account context.
  function handleReset() {
    setChatId(null);
    setMessages([]);
    setWorkflowResult(null);
    setWorkflowSteps([]);
    setWorkflowStatus('idle');
    setErrorMessage(null);
    setPrompt(DEFAULT_PROMPT);
  }

  return (
    <main className="workspace">
      <section className="topbar" aria-label="Application header">
        <div>
          <p className="eyebrow">JSON-backed prototype</p>
          <h1>Product Recommendation Workspace</h1>
        </div>
        <div className="statusPill">
          <CheckCircle2 size={16} aria-hidden="true" />
          FastAPI + LangGraph
        </div>
      </section>

      <section className="workspaceGrid">
        <aside className="contextPanel" aria-label="Recommendation context">
          <PanelHeader
            icon={<Building2 size={18} aria-hidden="true" />}
            title="Account Context"
          />
          <label className="field">
            <span>Account</span>
            <select
              value={selectedAccountId}
              onChange={(event) => setSelectedAccountId(event.target.value)}
            >
              {accounts.map((account) => (
                <option key={account.id} value={account.id}>
                  {account.name}
                </option>
              ))}
            </select>
          </label>
          <label className="field">
            <span>Opportunity</span>
            <select
              value={selectedOpportunityId}
              onChange={(event) => setSelectedOpportunityId(event.target.value)}
            >
              {opportunities.map((opportunity) => (
                <option key={opportunity.id} value={opportunity.id}>
                  {opportunity.name}
                </option>
              ))}
            </select>
          </label>
          <ContextSummary account={selectedAccount} opportunity={selectedOpportunity} />
          <div className="promptStack">
            <p className="sectionLabel">Sample requests</p>
            {SAMPLE_REQUESTS.map((sample) => (
              <button
                className="sampleButton"
                key={sample.label}
                onClick={() => setPrompt(sample.prompt)}
                type="button"
              >
                <ArrowRight size={14} aria-hidden="true" />
                {sample.label}
              </button>
            ))}
          </div>
        </aside>

        <section className="chatPanel" aria-label="Recommendation chat">
          <PanelHeader
            icon={<MessageSquareText size={18} aria-hidden="true" />}
            title="Request"
          />
          <div className="messageList">
            {messages.length === 0 ? (
              <div className="emptyState">
                <Sparkles size={20} aria-hidden="true" />
                <span>Ready for a recommendation request.</span>
              </div>
            ) : (
              messages.map((message) => <MessageBubble key={message.id} message={message} />)
            )}
          </div>
          {errorMessage ? <div className="errorBox">{errorMessage}</div> : null}
          <form className="promptForm" onSubmit={handleSubmit}>
            <textarea
              aria-label="Recommendation request"
              onChange={(event) => setPrompt(event.target.value)}
              placeholder="Optional request; blank uses selected context"
              rows={5}
              value={prompt}
            />
            <div className="formActions">
              <button className="secondaryButton" onClick={handleReset} type="button">
                <RotateCcw size={16} aria-hidden="true" />
                Reset
              </button>
              <button className="primaryButton" disabled={isLoading} type="submit">
                {isLoading ? (
                  <Loader2 className="spin" size={16} aria-hidden="true" />
                ) : (
                  <Send size={16} aria-hidden="true" />
                )}
                Recommend
              </button>
            </div>
          </form>
        </section>

        <aside className="resultsPanel" aria-label="Recommendation results">
          <PanelHeader
            icon={<Sparkles size={18} aria-hidden="true" />}
            title="Good Better Best"
          />
          <ResultSummary workflowResult={workflowResult} />
          <RecommendationList
            isLoading={isLoading}
            recommendations={workflowResult?.recommendations ?? []}
          />
          <WorkflowSteps steps={workflowResult?.steps ?? workflowSteps} status={workflowStatus} />
        </aside>
      </section>
    </main>
  );
}

async function waitForWorkflowResult(
  workflowId: string,
  onStatus: (steps: WorkflowStep[], status: string) => void,
) {
  const startedAt = Date.now();

  // Poll status until the backend marks the staged workflow as terminal.
  while (Date.now() - startedAt < WORKFLOW_TIMEOUT_MS) {
    const status = await fetchWorkflowStatus(workflowId);
    onStatus(status.steps, status.status);
    if (status.terminal) {
      return fetchWorkflowResult(workflowId);
    }
    await delay(POLL_INTERVAL_MS);
  }

  // Fail visibly if the simulated workflow does not finish in time.
  throw new Error('Workflow did not finish within the local prototype timeout.');
}

function delay(durationMs: number): Promise<void> {
  // Use a small promise wrapper so polling reads clearly in the workflow loop.
  return new Promise((resolve) => window.setTimeout(resolve, durationMs));
}

function PanelHeader({
  icon,
  title,
}: {
  icon: ReactNode;
  title: string;
}) {
  // Render compact panel headings shared across the workspace.
  return (
    <div className="panelHeader">
      <span className="panelIcon">{icon}</span>
      <h2>{title}</h2>
    </div>
  );
}

function ContextSummary({
  account,
  opportunity,
}: {
  account: Account | null;
  opportunity: Opportunity | null;
}) {
  // Show selected context in a dense enterprise summary block.
  return (
    <div className="contextSummary">
      <div>
        <span>Industry</span>
        <strong>{account?.industry ?? '-'}</strong>
      </div>
      <div>
        <span>Country</span>
        <strong>{account?.country ?? '-'}</strong>
      </div>
      <div>
        <span>Stage</span>
        <strong>{opportunity?.stage ?? '-'}</strong>
      </div>
      <p>{opportunity?.summary ?? 'Select an account and opportunity.'}</p>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  // Separate user and assistant messages with restrained visual weight.
  return (
    <article className={`messageBubble ${message.role}`}>
      <span>{message.role === 'user' ? 'You' : 'Assistant'}</span>
      <p>{message.content}</p>
    </article>
  );
}

function ResultSummary({ workflowResult }: { workflowResult: WorkflowResult | null }) {
  // Keep result metrics visible even before the first recommendation.
  const recommendations = workflowResult?.recommendations ?? [];
  const topRecommendation = recommendations[0]?.product.name ?? '-';
  const averageScore =
    recommendations.length > 0
      ? Math.round(
          recommendations.reduce((total, item) => total + item.score, 0) /
            recommendations.length,
        )
      : 0;

  return (
    <div className="resultSummary">
      <Metric label="Cards" value={recommendations.length.toString()} />
      <Metric label="Avg score" value={averageScore ? averageScore.toString() : '-'} />
      <Metric label="Top match" value={topRecommendation} wide />
    </div>
  );
}

function Metric({
  label,
  value,
  wide,
}: {
  label: string;
  value: string;
  wide?: boolean;
}) {
  // Render stable metric cells so values do not shift the panel layout.
  return (
    <div className={wide ? 'metric metricWide' : 'metric'}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function RecommendationList({
  isLoading,
  recommendations,
}: {
  isLoading: boolean;
  recommendations: RecommendationOption[];
}) {
  // Show an empty state until the backend returns ranked cards.
  if (isLoading && recommendations.length === 0) {
    return <div className="cardsEmpty">Workflow is ranking recommendations.</div>;
  }

  // Show an empty state until the first completed recommendation.
  if (recommendations.length === 0) {
    return <div className="cardsEmpty">No recommendations loaded yet.</div>;
  }

  return (
    <div className="cardStack">
      {recommendations.map((recommendation) => (
        <RecommendationCard
          key={recommendation.product.id}
          recommendation={recommendation}
        />
      ))}
    </div>
  );
}

function RecommendationCard({
  recommendation,
}: {
  recommendation: RecommendationOption;
}) {
  const { product } = recommendation;

  // Present each ranked option as a compact product card.
  return (
    <article className="productCard">
      <div className="productImageWrap">
        <img alt={product.name} className="productImage" src={product.image_url} />
        <span className={`badge badge${recommendation.badge}`}>{recommendation.badge}</span>
      </div>
      <div className="productBody">
        <div className="productTitleRow">
          <div>
            <h3>{product.name}</h3>
            <p>
              {product.category} - {product.form_factor}
            </p>
          </div>
          <strong>${product.price_usd.toLocaleString()}</strong>
        </div>
        <p className="reasoning">{recommendation.reasoning}</p>
        <div className="specGrid">
          <Spec label="CPU" value={product.specs.processor} />
          <Spec label="Memory" value={`${product.specs.memory_gb}GB`} />
          <Spec label="Storage" value={`${product.specs.storage_gb}GB`} />
          <Spec label="GPU" value={product.specs.gpu} />
        </div>
        <div className="tagRow">
          {recommendation.matched_requirements.slice(0, 5).map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </div>
        <div className="stockRow">
          <span>{product.inventory.status}</span>
          <span>{product.inventory.quantity} units</span>
          <span>Score {recommendation.score}</span>
        </div>
      </div>
    </article>
  );
}

function Spec({ label, value }: { label: string; value: string }) {
  // Keep hardware specs scannable in a fixed two-line cell.
  return (
    <div className="specCell">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function WorkflowSteps({ steps, status }: { steps: WorkflowStep[]; status: string }) {
  // Render LangGraph receipts under the product cards.
  return (
    <div className="workflowBox">
      <div className="workflowHeader">
        <p className="sectionLabel">Workflow receipts</p>
        <span className={`workflowStatus ${status}`}>{status}</span>
      </div>
      {steps.length === 0 ? (
        <span className="mutedLine">Waiting for LangGraph output.</span>
      ) : (
        steps.map((step) => (
          <div className={`workflowStep ${step.status}`} key={step.id}>
            <StepIcon status={step.status} />
            <div>
              <strong>{step.label}</strong>
              <span>{step.detail}</span>
            </div>
          </div>
        ))
      )}
    </div>
  );
}

function StepIcon({ status }: { status: string }) {
  // Match the icon to the current stage state.
  if (status === 'completed') {
    return <CheckCircle2 size={15} aria-hidden="true" />;
  }
  if (status === 'running') {
    return <Loader2 className="spin" size={15} aria-hidden="true" />;
  }
  return <Circle size={15} aria-hidden="true" />;
}

function readErrorMessage(error: unknown): string {
  // Convert unknown runtime errors into a useful UI message.
  if (error instanceof Error) {
    return error.message;
  }
  return 'Unexpected request failure.';
}
