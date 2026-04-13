import { Mail, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CONTACT } from "@/lib/constants/urls";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

interface ContactModalProps {
  isOpen: boolean;
  onOpenChange: (open: boolean) => void;
  trigger: React.ReactNode;
}

export function ContactModal({
  isOpen,
  onOpenChange,
  trigger,
}: ContactModalProps) {
  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <div className="rounded-full bg-yellow-bright p-2">
              <Mail className="size-5 text-gray-900" />
            </div>
            Contact Us to Upgrade
          </DialogTitle>
          <DialogDescription className="pt-4">
            Get access to all integrations with Business or Enterprise plans.
            Contact our team to discuss your needs and activate integrations.
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 pt-4">
          <div className="rounded-lg border border-yellow-bright/30 bg-yellow-light/30 p-4">
            <div className="flex items-start gap-3">
              <div className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-yellow-bright">
                <Mail className="size-5 text-gray-900" />
              </div>
              <div className="flex-1">
                <p className="text-sm font-semibold text-gray-900">
                  Talk to our founder
                </p>
                <p className="mt-1 text-sm text-gray-600">
                  Email{" "}
                  <a
                    href={CONTACT.MAILTO}
                    className="font-semibold text-ai-brown underline decoration-ai-brown/30 underline-offset-2 transition-colors hover:text-ai-brown/80"
                  >
                    {CONTACT.EMAIL}
                  </a>
                </p>
              </div>
            </div>
          </div>
          <div className="flex gap-2">
            <Button className="flex-1 gap-2" asChild>
              <a href={CONTACT.MAILTO}>
                <Mail className="size-4" />
                Send Email
              </a>
            </Button>
            <Button variant="outline" className="flex-1" asChild>
              <a
                href="/pricing"
                target="_blank"
                rel="noopener noreferrer"
              >
                View Pricing
                <ExternalLink className="ml-2 size-4" />
              </a>
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
