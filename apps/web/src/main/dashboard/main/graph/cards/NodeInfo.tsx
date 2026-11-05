type Props = {
    label: string;
    color?: string;
    description?: string;
    attributes?: Record<string, unknown>;
};

export default function NodeInfo({
    label,
    color,
    description,
    attributes = {},
}: Props) {
    return (
        <div className="w-80 p-5 text-[#ececec] font-mono">
            <div className="flex justify-center items-center mb-[15px]">
                <h3 className="m-0" style={{ color }}>
                    {label}
                </h3>
            </div>

            <div className="text-[12px] text-[#aaa] mb-[15px] border-b border-[#333] pb-[15px]">
                {description}
            </div>

            <div className="text-[12px]">
                <div
                    className="mb-2 uppercase tracking-[1px]"
                    style={{ color }}
                >
                    Attributes
                </div>
                {Object.entries(attributes).map(([key, value]) => (
                    <div key={key} className="mb-[6px] flex flex-col">
                        <span className="text-[#888]">
                            {key.replace(/_/g, " ")}:
                        </span>
                        <span className="text-white">
                            {Array.isArray(value)
                                ? value.join(", ")
                                : String(value)}
                        </span>
                    </div>
                ))}
            </div>
        </div>
    );
}
